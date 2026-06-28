#!/usr/bin/env python3
"""
extract_figures.py -- pull figures out of a scientific PDF *exactly as they appear*.

Why region-rendering instead of raw image extraction:
  A paper's figure is rarely a single clean raster. It's often a composite of
  several embedded images, vector plots (axes, curves drawn as paths), and text
  labels laid on top. `pdfimages` / get_images() return the raw embedded rasters,
  which means vector plots vanish, multi-panel figures shatter into pieces, and
  axis labels disappear. Instead we locate the *region* of the page that the
  figure occupies (its images + vector drawings, grouped by the caption that
  describes them) and render that rectangle at high DPI. What you get is a pixel-
  faithful snapshot of the figure as a human sees it -- panels, plots, labels,
  everything -- which is exactly the fidelity this skill promises.

Output:
  <out>/figures/<id>.png           one image per detected figure/table
  <out>/figures/manifest.json      [{id,label,caption,page,bbox,image,kind}]
  <out>/figures/pages/             (only with --debug) full-page renders

Usage:
  python extract_figures.py --pdf paper.pdf --out ./build [--dpi 200] [--debug]
"""
import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required:  pip install pymupdf")

# "Figure 1", "Fig. 2:", "FIGURE 3 |", "Table 1", "Scheme 2", "Algorithm 1" ...
CAPTION_RE = re.compile(
    r"^\s*(figure|fig|table|scheme|chart|algorithm|listing|plate)\s*\.?\s*"
    r"(\d{1,3}|[ivxlc]{1,5})\b",
    re.IGNORECASE,
)

# A standalone panel sub-caption: a block that STARTS with "(a)", "(b)", ...
# These mark continuation panels of the *current* figure — sometimes on a later
# page with no "Figure N" caption of their own (which is how a sub-panel like
# "Figure 3b" goes missing). We only treat them as panels when an orphaned graphic
# sits next to them.
SUBCAP_RE = re.compile(r"^\s*\(([a-z])\)[\s.:,]", re.IGNORECASE)


def caption_label(text):
    m = CAPTION_RE.match(text)
    if not m:
        return None
    kind = m.group(1).lower()
    kind = {"fig": "figure"}.get(kind, kind)
    return f"{kind.capitalize()} {m.group(2).upper() if not m.group(2).isdigit() else m.group(2)}"


def rect_area(r):
    return max(0.0, r.x1 - r.x0) * max(0.0, r.y1 - r.y0)


def collect_visuals(page):
    """Bounding boxes of things that are *drawn* (images + meaningful vector art)."""
    page_rect = page.rect
    page_area = rect_area(page_rect)
    visuals = []

    for info in page.get_image_info():
        r = fitz.Rect(info["bbox"])
        if rect_area(r) > 0:
            visuals.append(("image", r))

    for d in page.get_drawings():
        r = fitz.Rect(d["rect"])
        w, h = r.x1 - r.x0, r.y1 - r.y0
        if w <= 2 or h <= 2:
            continue  # hairline rules, underlines, table borders-as-noise
        if rect_area(r) > 0.97 * page_area:
            continue  # full-page background boxes
        # full-width, very short -> a horizontal rule, not figure content
        if w > 0.9 * (page_rect.x1 - page_rect.x0) and h < 4:
            continue
        visuals.append(("drawing", r))
    return visuals


def find_captions(page):
    caps = []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        label = caption_label(text)
        if label:
            caps.append({
                "label": label,
                "caption": " ".join(text.split()).strip(),
                "rect": fitz.Rect(x0, y0, x1, y1),
            })
    return caps


def find_subcaptions(page):
    subs = []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        m = SUBCAP_RE.match(text)
        if m:
            subs.append({
                "letter": m.group(1).lower(),
                "caption": " ".join(text.split()).strip(),
                "rect": fitz.Rect(x0, y0, x1, y1),
            })
    return subs


def caption_visual_gap(cap_rect, vis_rect):
    """Vertical gap between a caption and a figure graphic; 0 if they overlap.

    Direction-agnostic on purpose: captions live *below* their figure in some
    templates and *above* it in others (and a single paper can mix both), so we
    measure the nearest-edge distance either way rather than assuming a side.
    """
    below = cap_rect.y0 - vis_rect.y1  # caption sits below the visual
    above = vis_rect.y0 - cap_rect.y1  # caption sits above the visual
    return max(0.0, below, above)


def horizontally_related(cap_rect, vis_rect, page_rect):
    """Guard against grabbing a neighbouring column's figure: the caption and the
    graphic should share some horizontal span (full-width captions match anything)."""
    overlap = min(cap_rect.x1, vis_rect.x1) - max(cap_rect.x0, vis_rect.x0)
    if overlap > 0:
        return True
    page_w = page_rect.x1 - page_rect.x0
    return (cap_rect.x1 - cap_rect.x0) > 0.6 * page_w  # spans the page -> single column


def assign_visuals_to_captions(captions, visuals, page_rect):
    """Bind each figure graphic to its nearest caption (above or below it).

    Using nearest-edge vertical gap (with a light horizontal sanity check)
    naturally partitions a page holding two or three figures and copes with both
    caption-above and caption-below layouts without a hard-coded rule.
    """
    groups = {i: [] for i in range(len(captions))}
    if not captions:
        return groups
    for kind, r in visuals:
        best, best_gap = None, 1e9
        for i, c in enumerate(captions):
            if not horizontally_related(c["rect"], r, page_rect):
                continue
            g = caption_visual_gap(c["rect"], r)
            if g < best_gap:
                best, best_gap = i, g
        if best is not None and best_gap < page_rect.height * 0.5:
            groups[best].append(r)
    return groups


def union(rects):
    r = fitz.Rect(rects[0])
    for x in rects[1:]:
        r |= fitz.Rect(x)
    return r


def expand_for_labels(page, region, caption_rect):
    """Grow the region to swallow panel titles/labels that sit just above the
    graphic. Plots often carry their title as *text* a few points above the
    image box (e.g. "Scaled Dot-Product Attention"), which a visuals-only union
    would clip. We only pull in SHORT text blocks that are horizontally inside
    the figure and within a small gap of its top edge, so body paragraphs and
    the caption are never swept in.
    """
    new = fitz.Rect(region)
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        r = fitz.Rect(x0, y0, x1, y1)
        if caption_rect is not None and r.intersects(caption_rect):
            continue
        t = " ".join(text.split())
        if not t or len(t) > 70:  # paragraphs are long; panel labels are short
            continue
        cx = (x0 + x1) / 2
        overlap = min(x1, region.x1) - max(x0, region.x0)
        horizontally_ok = (region.x0 - 3 <= cx <= region.x1 + 3) or overlap > 0.5 * (x1 - x0)
        gap = region.y0 - y1  # label's bottom sits this far above the region top
        if horizontally_ok and -3 <= gap <= 26:
            new |= r  # swallow the whole label, widening the region as needed
    return new


def clip_off_text(region, cap_rects):
    """Keep caption / sub-caption text out of the rendered figure. Trims the region
    at top or bottom for any caption block that intrudes on an edge — so a figure
    whose sub-caption sits 1pt below it doesn't leave a leftover strip of caption in
    the crop. Only edge captions are trimmed (top 40% / bottom 40%), never one that
    sits mid-figure between panels."""
    r = fitz.Rect(region)
    h = r.y1 - r.y0
    if h <= 0:
        return r
    for c in cap_rects:
        if c.y1 <= r.y0 or c.y0 >= r.y1:                       # no vertical overlap
            continue
        if min(c.x1, r.x1) - max(c.x0, r.x0) <= 0:             # no horizontal overlap
            continue
        cmid = (c.y0 + c.y1) / 2
        if cmid >= r.y0 + 0.6 * h:                             # caption near the bottom
            r.y1 = min(r.y1, c.y0 - 2)
        elif cmid <= r.y0 + 0.4 * h:                           # caption near the top
            r.y0 = max(r.y0, c.y1 + 2)
    return r


def slugify(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True, help="output dir (figures/ is created inside)")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--pad", type=float, default=12.0, help="pts of padding around a figure region")
    ap.add_argument("--debug", action="store_true", help="also dump full-page renders")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    figdir = Path(args.out) / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    zoom = args.dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    manifest = []
    seen_ids = {}

    def render_and_record(anchor, page, pno, cap_rects):
        rects = anchor["rects"]
        kind = anchor["kind"]
        uid = anchor["id"]
        seen_ids[uid] = seen_ids.get(uid, 0) + 1
        if seen_ids[uid] > 1:
            uid = f"{uid}-{seen_ids[uid]}"

        if rects:
            region = union(rects)
            region = expand_for_labels(page, region, anchor["cap_rect"])
            region = fitz.Rect(region.x0 - args.pad, region.y0 - args.pad,
                               region.x1 + args.pad, region.y1 + args.pad)
            region = clip_off_text(region, cap_rects)   # trim any caption/sub-caption strip
            region &= page.rect
        else:
            # No graphic near the caption — usually a text-only table (rebuild as HTML).
            # Best-effort band on the side the content lives: tables below, figures above.
            c = anchor["cap_rect"]
            if kind == "tables":
                bottom = min(page.rect.y1, c.y1 + page.rect.height * 0.45)
                region = fitz.Rect(page.rect.x0, c.y1 + 2, page.rect.x1, bottom)
            else:
                top = max(page.rect.y0, c.y0 - page.rect.height * 0.4)
                region = fitz.Rect(page.rect.x0, top, page.rect.x1, c.y0 - 2)
            region &= page.rect

        img_path = None
        if rect_area(region) >= 100:
            pix = page.get_pixmap(matrix=mat, clip=region)
            img_name = f"{uid}.png"
            pix.save(str(figdir / img_name))
            img_path = f"figures/{img_name}"

        manifest.append({
            "id": uid, "label": anchor["label"], "caption": anchor["caption"],
            "page": pno + 1,
            "bbox": [round(v, 1) for v in (region.x0, region.y0, region.x1, region.y1)],
            "image": img_path, "kind": kind, "localized": bool(rects),
        })

    cur_fig_num = None  # numeric part of the most recent "Figure N", carried across pages
    for pno in range(len(doc)):
        page = doc[pno]
        mains = find_captions(page)
        subs = find_subcaptions(page)
        visuals = collect_visuals(page)

        if args.debug and (mains or subs or visuals):
            (figdir / "pages").mkdir(exist_ok=True)
            page.get_pixmap(matrix=mat).save(str(figdir / "pages" / f"page-{pno+1}.png"))

        fig_in = cur_fig_num                       # figure in progress *coming into* this page
        for c in mains:                            # update running figure number
            if c["label"].lower().startswith("figure"):
                cur_fig_num = c["label"].split()[1]

        cap_rects = [c["rect"] for c in mains] + [s["rect"] for s in subs]

        anchors = []
        groups = assign_visuals_to_captions(mains, visuals, page.rect)
        claimed = set()
        for i, c in enumerate(mains):
            rs = groups.get(i, [])
            for r in rs:
                claimed.add(id(r))
            anchors.append({
                "label": c["label"], "id": slugify(c["label"]),
                "kind": "tables" if c["label"].lower().startswith("table") else "figure",
                "caption": c["caption"], "cap_rect": c["rect"], "rects": rs,
            })

        # Graphics with no main caption nearby are continuation panels of the figure
        # in progress (e.g. "Figure 3b" on a later page) — group them by the
        # "(b)/(c)…" sub-caption they sit beside.
        orphaned = [(k, r) for (k, r) in visuals if id(r) not in claimed]
        if orphaned and subs and fig_in:
            subgroups = {}
            for k, r in orphaned:
                best, best_gap = None, 1e9
                for s in subs:
                    if not horizontally_related(s["rect"], r, page.rect):
                        continue
                    g = caption_visual_gap(s["rect"], r)
                    if g < best_gap:
                        best, best_gap = s, g
                if best is not None and best_gap < page.rect.height * 0.5:
                    subgroups.setdefault(best["letter"], {"sub": best, "rects": []})["rects"].append(r)
            for letter, sg in sorted(subgroups.items()):
                anchors.append({
                    "label": f"Figure {fig_in}{letter}", "id": f"figure-{fig_in}-{letter}",
                    "kind": "figure", "caption": sg["sub"]["caption"],
                    "cap_rect": sg["sub"]["rect"], "rects": sg["rects"],
                })

        for a in anchors:
            render_and_record(a, page, pno, cap_rects)

    (figdir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Extracted {sum(1 for m in manifest if m['image'])} figure images "
          f"({len(manifest)} captions seen) -> {figdir}")
    not_loc = [m["label"] for m in manifest if not m["localized"]]
    if not_loc:
        print(f"[!] Could not localize graphics for: {', '.join(not_loc)} "
              f"(used fallback region; eyeball these, or rerun with --debug).")


if __name__ == "__main__":
    main()
