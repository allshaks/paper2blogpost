# paper2blogpost

A Claude Code skill that turns a scientific paper PDF into a warm, colloquial,
**self-contained HTML blog post** — keeping every figure, equation, table, and
reference intact. It's a faithful *translation of register* (stiff academic prose →
natural conversational language), **not** a summary and not a dumbing-down: a domain
expert should enjoy this version *more* than the original. Same depth, same rigor,
friendlier delivery.

## What it produces

A single folder you can open or hand to anyone:

```
<paper-name>-blogpost/
├── index.html   # the post: design + content + inlined citation data
├── figures/     # figures, reproduced pixel-faithfully from the PDF
└── refs/        # the citation data (refs.json), inspectable
```

Highlights:

- **Section-by-section translation** into plain language — no content dropped, every
  number, caveat, and nuance kept.
- **Pixel-faithful figures** (multi-panel / multi-page aware); tables rebuilt as real
  HTML rather than screenshots.
- **Every reference kept**, with hover popups and a lazy, web-grounded *"What is it
  about?"* summary (Claude Haiku, the reader's own key, cached in the browser).
- **Live cross-references** — hover "Figure 3" / "Eq. 1" / "Table 2" to peek, click to
  jump.
- **Numbered citations**, clickable DOI / arXiv / URL links, a translucent table of
  contents, a reading-progress bar, light/dark, and real rendered math (MathJax).
- **Optional local chat** woven into the post (see below).

## Usage

This is a skill for Claude Code / the Claude Agent SDK: point Claude at a PDF and ask
for a colloquial blog-post version. The full workflow Claude follows lives in
[`paper2blogpost/SKILL.md`](paper2blogpost/SKILL.md).

The extractors need PyMuPDF:

```bash
pip install pymupdf
```

The pipeline (Claude runs these as it works through `SKILL.md`):

```bash
BUILD="<paper-slug>-build"          # unique per paper
python paper2blogpost/scripts/extract_text.py    --pdf paper.pdf --out "$BUILD"
python paper2blogpost/scripts/extract_figures.py --pdf paper.pdf --out "$BUILD" --dpi 200
# … translate section by section into $BUILD/sections/ …
python paper2blogpost/scripts/assemble.py --build "$BUILD" \
  --template paper2blogpost/assets/template.html --out "$BUILD/index.html"
```

## Optional: local chat mode

The post can gain a collapsible **sidebar chat** that answers questions about the
paper, grounded in its full text and running locally through the reader's `claude`
CLI — no API key, it uses your Claude Code login. It shows **live agent activity**
(thinking · searching the web · reading), with model + effort pickers, an internet
toggle, multiple threads, and select-text → **Ask** / **Rewrite** with persistent
highlights. The chat UI ships hidden in every post and only lights up when the
companion server is running.

```bash
cp "$BUILD/text/full.txt" "<post>/chat/paper.md"        # grounding text
python paper2blogpost/scripts/chat-server.py --dir "<post>"
# open the printed http://127.0.0.1:8765/ URL and click "💬 Ask Claude"
```

See [`paper2blogpost/references/chat-mode.md`](paper2blogpost/references/chat-mode.md).

## Layout

```
paper2blogpost/
├── SKILL.md                  # the workflow Claude follows
├── scripts/                  # extract_text, extract_figures, assemble, chat-server
├── assets/template.html      # the entire design (HTML + CSS + JS, inline)
├── references/               # authoring conventions, design notes, popups, chat mode
└── evals/evals.json          # skill-creator eval benchmark
```

See [ROADMAP.md](ROADMAP.md) for what's shipped and what's next.
