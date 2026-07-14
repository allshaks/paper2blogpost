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

Two post modes share this one template: 'full' (default — a complete colloquial
translation, nothing dropped) and 'concise' (a short LessWrong-style summary). The
mode rides on a `body.concise` class so the design (Summary badge, TL;DR box) is
styled centrally; pass --mode or set "mode" in meta.json. --upgrade preserves it.

Usage:
  # assemble a fresh post from a build dir (full is the default):
  python assemble.py --build ./build --template ../assets/template.html --out ./build/index.html

  # assemble a concise summary post:
  python assemble.py --build ./build --out ./build/index.html --mode concise

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

# ---- cross-reference auto-linker -------------------------------------------------
# The model is unreliable at wrapping in-text mentions ("Theorem 20", "Definition 3")
# in <a class="xref">, especially for formal statements and forward references (whose
# target box is written in a later section). So after stitching we do it deterministically:
# wrap every unlinked "Kind N" mention whose target id actually exists in the article.
# Guards: it never touches text inside a tag/attribute, an existing <a>, a heading, code,
# or a box's own label (so it can't self-link or corrupt markup); and it only links when
# the derived id is really present, so a stray "Table 9" with no table-9 stays plain.
#
# Each kind maps to the id-prefixes to TRY, canonical (abbreviated) form first — the one
# authoring.md tells the model to use — then the full word, since generated ids vary in
# practice (some posts write `lemma-2`/`example-6`, others `lem-2`/`ex-6`). We link to the
# first candidate id that actually exists, so the linker is robust to either convention.
XREF_PREFIXES = {
    'theorem': ['thm', 'theorem'], 'thm': ['thm', 'theorem'],
    'lemma': ['lem', 'lemma'], 'lem': ['lem', 'lemma'],
    'proposition': ['prop', 'proposition'], 'prop': ['prop', 'proposition'],
    'corollary': ['cor', 'corollary'], 'cor': ['cor', 'corollary'],
    'definition': ['def', 'definition'], 'def': ['def', 'definition'],
    'assumption': ['assum', 'assumption', 'asm'],
    'claim': ['claim'], 'conjecture': ['conj', 'conjecture'], 'fact': ['fact'],
    'remark': ['rem', 'remark'], 'example': ['ex', 'example', 'eg'],
    'note': ['note'], 'observation': ['obs', 'observation'],
    'figure': ['figure', 'fig'], 'fig': ['figure', 'fig'],
    'equation': ['eq', 'equation'], 'eq': ['eq', 'equation'], 'eqn': ['eq', 'equation'],
    'table': ['table', 'tbl'], 'algorithm': ['algorithm', 'alg'], 'alg': ['algorithm', 'alg'],
}
# Regions to copy through verbatim (never link inside them). Ordered: whole protected
# blocks first, then any single tag (so attribute text like alt="Figure 2" is untouched).
_XREF_PROTECT = re.compile(
    r'<a\b[^>]*>.*?</a>'                                             # existing links
    r'|<(h[1-6])\b[^>]*>.*?</\1>'                                    # headings
    r'|<(code|pre|script|style)\b[^>]*>.*?</\2>'                     # code / scripts
    r'|<span\b[^>]*\bclass="[^"]*\b(?:thm-label|figlabel)\b[^"]*"[^>]*>.*?</span>'  # a box/figure's own label
    r'|<[^>]+>',                                                     # any other single tag
    re.DOTALL | re.IGNORECASE)
# Case-SENSITIVE, capitalized kind (so lowercase prose like "figure out" / "note 3 things"
# is left alone) + a number (dotted numbering allowed, optional trailing sub-letter).
_XREF_MENTION = re.compile(
    r'\b(Theorem|Thm\.?|Lemma|Lem\.?|Proposition|Prop\.?|Corollary|Cor\.?|Definition|Def\.?'
    r'|Assumption|Claim|Conjecture|Fact|Remark|Example|Note|Observation'
    r'|Figure|Fig\.?|Equation|Eq\.?|Eqn\.?|Table|Algorithm|Alg\.?)\s+(\d+(?:\.\d+)*[a-z]?)\b')


def autolink_xrefs(content: str):
    """Wrap unlinked 'Kind N' mentions in <a class="xref"> when the target id exists in the
    article. Returns (new_content, count). Idempotent (skips existing <a>)."""
    idset = set(re.findall(r'\bid="([^"]+)"', content))
    if not idset:
        return content, 0
    added = [0]

    def wrap(m):
        cands = XREF_PREFIXES.get(m.group(1).rstrip('.').lower())
        if not cands:
            return m.group(0)
        num = m.group(2).replace('.', '-')
        for p in cands:
            tid = f'{p}-{num}'
            if tid in idset:                        # first existing target wins
                added[0] += 1
                return f'<a class="xref" data-target="{tid}">{m.group(0)}</a>'
        return m.group(0)                           # no such target -> leave the text plain

    out, last = [], 0
    for mo in _XREF_PROTECT.finditer(content):
        gap = content[last:mo.start()]              # plain text between protected regions
        if gap:
            out.append(_XREF_MENTION.sub(wrap, gap))
        out.append(mo.group(0))                     # protected region / tag: verbatim
        last = mo.end()
    tail = content[last:]
    if tail:
        out.append(_XREF_MENTION.sub(wrap, tail))
    return ''.join(out), added[0]


def default_template() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "template.html"


def fill(template: str, repl: dict) -> str:
    """Fill {{PLACEHOLDER}} tokens in one pass, so a value that happens to contain a
    token string can't be clobbered by a later replacement."""
    return PLACEHOLDER_RE.sub(lambda m: repl.get(m.group(0), m.group(0)), template)


def build_post(build: Path, template_path: Path, out: Path, mode: str = None):
    template = template_path.read_text()
    meta = json.loads((build / "meta.json").read_text())
    # 'full' (default) keeps all content; 'concise' emits a summary post. The mode
    # rides on a body class so the template styles both from one file (Summary badge,
    # TL;DR box). --mode overrides; else meta.json's "mode"; else full.
    mode = mode or meta.get("mode") or "full"
    body_class = ' class="concise"' if mode == "concise" else ""

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

    content, nlinks = autolink_xrefs("\n".join(content_parts))   # wrap missed "Theorem N"/… mentions

    out_html = fill(template, {
        "{{BODY_CLASS}}": body_class,
        "{{TITLE}}": title,
        "{{HERO_TITLE}}": meta.get("hero_title", title),
        "{{DEK}}": meta.get("dek", ""),
        "{{META}}": meta.get("meta_html", ""),
        "{{TOC}}": "\n".join(toc_parts),
        "{{CONTENT}}": content,
        "{{REFERENCES_LIST}}": ref_list,
        "{{REFS_DATA}}": json.dumps(refs_data, ensure_ascii=False).replace("</", "<\\/"),
        "{{PAPER_DATA}}": json.dumps(paper_data, ensure_ascii=False).replace("</", "<\\/"),
    })
    out.parent.mkdir(parents=True, exist_ok=True)   # so --out can point anywhere (e.g. the central store)
    out.write_text(out_html)

    # Make the post chat-ready automatically: drop the paper's full text where the chat
    # server grounds on it. Always the FULL extracted text — even for a concise summary
    # post, the chat should be able to answer about the parts the summary left out. (The
    # server still creates CLAUDE.md / threads.json itself, lazily.)
    grounded = False
    full_txt = build / "text" / "full.txt"
    if full_txt.exists():
        chat_dir = out.parent / "chat"
        chat_dir.mkdir(parents=True, exist_ok=True)
        (chat_dir / "paper.md").write_text(full_txt.read_text())
        grounded = True

    referenced = set(re.findall(r'<img[^>]+src=["\'](figures/[^"\']+)["\']', out_html))
    print(f"Wrote {out}  [{mode}]  ({len(section_files)} sections, {len(refs_data)} refs, "
          f"{len(referenced)} figures referenced, {nlinks} cross-ref links auto-added"
          f"{'; chat grounded' if grounded else '; no build/text/full.txt → chat ungrounded'}).")


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
        # preserve full/concise across a re-skin: carry the body's mode class forward.
        # Always a string (never None) so {{BODY_CLASS}} is never left as a literal token.
        "{{BODY_CLASS}}":      ' class="concise"' if re.search(r'<body[^>]*\sclass="[^"]*\bconcise\b', html, re.I) else "",
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

    # retro-fix missed internal links on the extracted article (idempotent — skips existing <a>)
    nlinks = 0
    if fields.get("{{CONTENT}}"):
        fields["{{CONTENT}}"], nlinks = autolink_xrefs(fields["{{CONTENT}}"])

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
    print(f"  auto-added {nlinks} internal cross-ref links (Theorem/Definition/Figure/… mentions)")
    print(f"  backup of the old post: {backup}")
    if leftover:
        print(f"  ⚠ the new template has placeholders the old post didn't provide: {', '.join(leftover)} "
              "(left unfilled — the extractor may need updating for a newer template).")


def main():
    ap = argparse.ArgumentParser(description="Assemble a paper2blogpost, or upgrade an existing one.")
    ap.add_argument("--build", help="build dir (sections/, meta.json, refs.json, references_list.html)")
    ap.add_argument("--template", help="template.html (default: the skill's own assets/template.html)")
    ap.add_argument("--out", help="output index.html (assembly mode)")
    ap.add_argument("--mode", choices=["full", "concise"], default=None,
                    help="'full' (default) keeps every bit of content; 'concise' marks the post as a "
                         "LessWrong-style summary (Summary badge + body.concise styling). If omitted, "
                         "falls back to meta.json's \"mode\", else full.")
    ap.add_argument("--upgrade", metavar="POST",
                    help="re-skin an already-assembled post (its folder or index.html) to the current "
                         "template — no build/ dir needed. Backs up the old index.html to index.html.bak.")
    args = ap.parse_args()
    template_path = Path(args.template) if args.template else default_template()

    if args.upgrade:
        return upgrade_post(args.upgrade, template_path)
    if not args.build or not args.out:
        ap.error("assembly needs --build and --out (or use --upgrade to re-skin an existing post).")
    build_post(Path(args.build), template_path, Path(args.out), mode=args.mode)


if __name__ == "__main__":
    main()
