#!/usr/bin/env python3
"""
assemble.py -- stitch the translated pieces into the final blogpost, or re-skin an
existing post to the latest template.

The skill translates the paper one section at a time, writing each to its own
file. Assembly gathers those pieces, fills the design template, and derives the
table of contents automatically from each section's id + <h2>, so the model never
has to keep a separate TOC in sync by hand.

Expected build layout (created by the skill as it works):
  <build>/meta.json              {title, hero_title, dek, meta_html}
  <build>/sections/*.html        sorted by filename; each a <section id="..."><h2>...</h2>...</section>
  <build>/references_list.html   the bibliography (an <ol> of <li id="ref-N">...)
  <build>/refs.json              {"ref-N": {num, citation, summary, relevance}}
  <build>/figures/               figure images referenced by the sections

Usage:
  # assemble a fresh post from a build dir:
  python assemble.py --build ./build --template ../assets/template.html --out ./build/index.html

  # re-skin an ALREADY-assembled post to the current template (no build/ dir needed) —
  # picks up template improvements (new features, fixes) in place; backs up index.html:
  python assemble.py --upgrade <post-dir-or-index.html>
"""
import argparse
import json
import re
from pathlib import Path

SEC_ID_RE = re.compile(r'<section[^>]*\bid="([^"]+)"', re.IGNORECASE)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")


def default_template() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "template.html"


def fill(template: str, repl: dict) -> str:
    """Fill {{PLACEHOLDER}} tokens in one pass, so a value that happens to contain a
    token string can't be clobbered by a later replacement."""
    return PLACEHOLDER_RE.sub(lambda m: repl.get(m.group(0), m.group(0)), template)


def build_post(build: Path, template_path: Path, out: Path):
    template = template_path.read_text()
    meta = json.loads((build / "meta.json").read_text())

    section_files = sorted((build / "sections").glob("*.html"))
    if not section_files:
        raise SystemExit("No section files found in build/sections/ -- translate sections first.")

    content_parts, toc_parts = [], []
    for f in section_files:
        html = f.read_text()
        content_parts.append(html)
        mid = SEC_ID_RE.search(html)
        mh2 = H2_RE.search(html)
        if mid and mh2:
            sid = mid.group(1)
            title = TAG_RE.sub("", mh2.group(1)).strip()
            toc_parts.append(f'    <li><a href="#{sid}">{title}</a></li>')
    toc_parts.append('    <li><a href="#references">References</a></li>')

    refs_data = {}
    refs_path = build / "refs.json"
    if refs_path.exists():
        refs_data = json.loads(refs_path.read_text())

    ref_list = ""
    rl_path = build / "references_list.html"
    if rl_path.exists():
        ref_list = rl_path.read_text()

    title = meta.get("title", "Paper")
    paper_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "paper"
    paper_data = {"title": title, "id": paper_id}

    out_html = fill(template, {
        "{{TITLE}}": title,
        "{{HERO_TITLE}}": meta.get("hero_title", title),
        "{{DEK}}": meta.get("dek", ""),
        "{{META}}": meta.get("meta_html", ""),
        "{{TOC}}": "\n".join(toc_parts),
        "{{CONTENT}}": "\n".join(content_parts),
        "{{REFERENCES_LIST}}": ref_list,
        "{{REFS_DATA}}": json.dumps(refs_data, ensure_ascii=False).replace("</", "<\\/"),
        "{{PAPER_DATA}}": json.dumps(paper_data, ensure_ascii=False).replace("</", "<\\/"),
    })
    out.write_text(out_html)
    referenced = set(re.findall(r'<img[^>]+src=["\'](figures/[^"\']+)["\']', out_html))
    print(f"Wrote {out}  ({len(section_files)} sections, {len(refs_data)} refs, "
          f"{len(referenced)} figures referenced).")


# --- upgrade: pull the filled content back out of an assembled post, re-stitch into
#     the current template. Anchors on stable structural landmarks the skill always
#     emits (the #toc <ul>, the .hero <h1>/.dek/.meta, the #references section, and the
#     __REFS__/__PAPER__ data), so it survives across template versions. ---
def extract_fields(html: str) -> dict:
    def grab(pattern, flags=re.DOTALL | re.IGNORECASE):
        m = re.search(pattern, html, flags)
        # strip the whitespace the template already puts around each placeholder, so
        # re-inserting doesn't stack blank lines (keeps repeated upgrades idempotent)
        return m.group(1).strip() if m else None
    return {
        "{{TITLE}}":           grab(r"<title>(.*?)</title>"),
        "{{TOC}}":             grab(r'<nav[^>]*id="toc"[^>]*>.*?<ul>(.*?)</ul>'),
        "{{HERO_TITLE}}":      grab(r'<header[^>]*class="hero"[^>]*>.*?<h1[^>]*>(.*?)</h1>'),
        "{{DEK}}":             grab(r'<p[^>]*class="dek"[^>]*>(.*?)</p>'),
        "{{META}}":            grab(r'<div[^>]*class="meta"[^>]*>(.*?)</div>\s*</header>'),
        "{{CONTENT}}":         grab(r'</header>(.*?)<section[^>]*id="references"'),
        "{{REFERENCES_LIST}}": grab(r'<section[^>]*id="references"[^>]*>.*?</h2>(.*?)</section>'),
        # these two are single-line JS assignments — match without DOTALL so `.` can't run past the line
        "{{REFS_DATA}}":       grab(r'window\.__REFS__\s*=\s*(\{.*\})\s*;', re.IGNORECASE),
        "{{PAPER_DATA}}":      grab(r'window\.__PAPER__\s*=\s*(\{.*\})\s*;', re.IGNORECASE),
    }


def upgrade_post(target: str, template_path: Path):
    p = Path(target)
    index = (p / "index.html") if p.is_dir() else p
    if not index.exists():
        raise SystemExit(f"No index.html at {index} — point --upgrade at a post folder or its index.html.")

    old = index.read_text()
    fields = extract_fields(old)
    # the content-bearing fields must be found, or this isn't a paper2blogpost post (or the
    # template's landmarks changed) — refuse rather than write a broken post.
    critical = ["{{TOC}}", "{{CONTENT}}", "{{REFERENCES_LIST}}", "{{REFS_DATA}}", "{{PAPER_DATA}}"]
    missing = [k for k in critical if not fields.get(k)]
    if missing:
        raise SystemExit(f"Couldn't extract {', '.join(missing)} from {index}. "
                         "Is it a post assembled by this skill? (Nothing was changed.)")

    new_html = fill(template_path.read_text(), {k: v for k, v in fields.items() if v is not None})
    leftover = sorted(set(PLACEHOLDER_RE.findall(new_html)))

    backup = index.with_name(index.name + ".bak")
    backup.write_text(old)
    index.write_text(new_html)

    try:
        nrefs = len(json.loads(fields["{{REFS_DATA}}"].replace("<\\/", "</")))
    except Exception:
        nrefs = "?"
    ntoc = fields["{{TOC}}"].count("<li")
    print(f"Upgraded {index}")
    print(f"  re-skinned to {template_path}")
    print(f"  carried over: {ntoc} TOC entries, {nrefs} references, and the full article + hero + meta")
    print(f"  backup of the old post: {backup}")
    if leftover:
        print(f"  ⚠ the new template has placeholders the old post didn't provide: {', '.join(leftover)} "
              "(left unfilled — the extractor may need updating for a newer template).")


def main():
    ap = argparse.ArgumentParser(description="Assemble a paper2blogpost, or upgrade an existing one.")
    ap.add_argument("--build", help="build dir (sections/, meta.json, refs.json, references_list.html)")
    ap.add_argument("--template", help="template.html (default: the skill's own assets/template.html)")
    ap.add_argument("--out", help="output index.html (assembly mode)")
    ap.add_argument("--upgrade", metavar="POST",
                    help="re-skin an already-assembled post (its folder or index.html) to the current "
                         "template — no build/ dir needed. Backs up the old index.html to index.html.bak.")
    args = ap.parse_args()
    template_path = Path(args.template) if args.template else default_template()

    if args.upgrade:
        return upgrade_post(args.upgrade, template_path)
    if not args.build or not args.out:
        ap.error("assembly needs --build and --out (or use --upgrade to re-skin an existing post).")
    build_post(Path(args.build), template_path, Path(args.out))


if __name__ == "__main__":
    main()
