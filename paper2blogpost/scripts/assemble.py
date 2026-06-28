#!/usr/bin/env python3
"""
assemble.py -- stitch the translated pieces into the final blogpost.

The skill translates the paper one section at a time, writing each to its own
file. This script gathers those pieces, fills the design template, and derives
the table of contents automatically from each section's id + <h2>, so the model
never has to keep a separate TOC in sync by hand.

Expected build layout (created by the skill as it works):
  <build>/meta.json              {title, hero_title, dek, meta_html}
  <build>/sections/*.html        sorted by filename; each a <section id="..."><h2>...</h2>...</section>
  <build>/references_list.html   the bibliography (an <ol> of <li id="ref-N">...)
  <build>/refs.json              {"ref-N": {num, citation, summary, relevance}}
  <build>/figures/               figure images referenced by the sections

Usage:
  python assemble.py --build ./build --template ../assets/template.html --out ./build/index.html
"""
import argparse
import json
import re
from pathlib import Path

SEC_ID_RE = re.compile(r'<section[^>]*\bid="([^"]+)"', re.IGNORECASE)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    build = Path(args.build)
    template = Path(args.template).read_text()

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
    # references entry in the TOC too
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

    out = template
    repl = {
        "{{TITLE}}": title,
        "{{HERO_TITLE}}": meta.get("hero_title", title),
        "{{DEK}}": meta.get("dek", ""),
        "{{META}}": meta.get("meta_html", ""),
        "{{TOC}}": "\n".join(toc_parts),
        "{{CONTENT}}": "\n".join(content_parts),
        "{{REFERENCES_LIST}}": ref_list,
        "{{REFS_DATA}}": json.dumps(refs_data, ensure_ascii=False).replace("</", "<\\/"),
        "{{PAPER_DATA}}": json.dumps(paper_data, ensure_ascii=False).replace("</", "<\\/"),
    }
    for k, v in repl.items():
        out = out.replace(k, v)

    Path(args.out).write_text(out)
    # count figures actually referenced in the post (build/figures/ may also hold
    # unused table-crop fallbacks the author chose to rebuild as HTML instead)
    referenced = set(re.findall(r'<img[^>]+src=["\'](figures/[^"\']+)["\']', out))
    print(f"Wrote {args.out}  ({len(section_files)} sections, {len(refs_data)} refs, "
          f"{len(referenced)} figures referenced).")


if __name__ == "__main__":
    main()
