#!/usr/bin/env python3
"""
extract_text.py -- dump a paper's text and a best-effort structural map.

The model *can* read a PDF directly, but re-rendering pages to read them again
and again is slow and token-hungry. This produces cheap artifacts to work from:

  <out>/text/full.txt        whole paper as text, with  ----- page N -----  markers
  <out>/structure.json       { title, headings:[{text,page,size}], references_start }

Heading detection is heuristic (font size larger than the body, line is short).
Treat it as a *suggestion*: the model should sanity-check the section list against
the actual paper, not trust this blindly.

Usage:
  python extract_text.py --pdf paper.pdf --out ./build
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("PyMuPDF is required:  pip install pymupdf")

REF_HEADING_RE = re.compile(r"^\s*(references|bibliography|works cited|literature cited)\s*$",
                            re.IGNORECASE)


def body_size(doc):
    """Most common rounded font size = body text."""
    sizes = Counter()
    for page in doc:
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes[round(span["size"])] += len(span.get("text", ""))
    return sizes.most_common(1)[0][0] if sizes else 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    outdir = Path(args.out)
    (outdir / "text").mkdir(parents=True, exist_ok=True)

    base = body_size(doc)
    heading_min = base + 1  # a heading is at least 1pt bigger than body text

    full = []
    headings = []
    references_start = None
    title = None

    for pno in range(len(doc)):
        page = doc[pno]
        full.append(f"\n----- page {pno+1} -----\n")
        full.append(page.get_text("text"))

        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                size = max(s["size"] for s in spans)
                # title: biggest text on page 1
                if pno == 0 and (title is None or size > title[1]) and len(text) > 8:
                    title = (text, size)
                if REF_HEADING_RE.match(text) and references_start is None:
                    references_start = {"page": pno + 1, "text": text}
                # candidate section heading: bigger than body, short, not a sentence
                if size >= heading_min and 2 <= len(text) <= 90 and text[-1] not in ".,;:":
                    headings.append({"text": text, "page": pno + 1, "size": round(size, 1)})

    (outdir / "text" / "full.txt").write_text("".join(full))
    structure = {
        "title": title[0] if title else None,
        "body_font_size": base,
        "headings": headings,
        "references_start": references_start,
        "num_pages": len(doc),
    }
    (outdir / "structure.json").write_text(json.dumps(structure, indent=2))
    print(f"Wrote text/full.txt and structure.json "
          f"({len(headings)} candidate headings, "
          f"references {'found p.'+str(references_start['page']) if references_start else 'NOT found'}).")


if __name__ == "__main__":
    main()
