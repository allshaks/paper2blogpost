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

## Install

`paper2blogpost` is a [Claude Code](https://claude.com/claude-code) **Agent Skill** — a
folder with a `SKILL.md` that Claude loads on demand. Installing one is just putting that
folder where Claude Code looks for skills:

| Scope | Put it in | Available |
|------|-----------|-----------|
| **Just you** | `~/.claude/skills/` | in every project |
| **One project** (shareable via the repo) | `<project>/.claude/skills/` | in that project |

```bash
git clone https://github.com/allshaks/paper2blogpost.git
mkdir -p ~/.claude/skills
cp -R paper2blogpost/paper2blogpost ~/.claude/skills/paper2blogpost   # repo/<skill> → skills dir

pip install pymupdf        # the figure/text extractors use PyMuPDF
```

The **folder name** (`paper2blogpost`) becomes the skill's name. To confirm it loaded,
type `/` in any Claude Code session and look for **paper2blogpost** in the list (or run
`/skills` for detail, `/doctor` to diagnose). Skills work the same across every Claude
Code surface — the CLI, the desktop app, and the VS Code / JetBrains extensions.

> Skills can also travel as **plugins**: if this one is published to a plugin marketplace
> you can install it that way instead and invoke it as `/paper2blogpost:paper2blogpost`.

## Usage

Two ways, both work:

- **Just ask.** Claude reads each installed skill's description and pulls this one in when it
  fits. In a session started where your PDF lives, say something like *"turn this paper into
  a friendly blog post"* or *"rewrite paper.pdf as a colloquial webpage"* — Claude takes it
  from there.
- **Invoke it explicitly** with the slash command — type `/paper2blogpost` and point it at
  your PDF.

Either way Claude works through [`paper2blogpost/SKILL.md`](paper2blogpost/SKILL.md):
it extracts the text and figures, translates the paper section by section, rebuilds the
tables and references, and assembles a self-contained `<paper-name>-blogpost/` folder
(the [structure above](#what-it-produces)). Open its `index.html` in any browser — done.

<details>
<summary><b>Under the hood</b> — the pipeline Claude runs for you</summary>

```bash
SK="$HOME/.claude/skills/paper2blogpost"
BUILD="<paper-slug>-build"          # unique per paper
python "$SK/scripts/extract_text.py"    --pdf paper.pdf --out "$BUILD"
python "$SK/scripts/extract_figures.py" --pdf paper.pdf --out "$BUILD" --dpi 200
# … translate section by section into $BUILD/sections/ …
python "$SK/scripts/assemble.py" --build "$BUILD" \
  --template "$SK/assets/template.html" --out "$BUILD/index.html"
```
</details>

## Optional: local chat mode

The post can gain a collapsible **sidebar chat** that answers questions about the
paper, grounded in its full text and running locally through the reader's `claude`
CLI — no API key, it uses your Claude Code login. It shows **live agent activity**
(thinking · searching the web · reading), with model + effort pickers, an internet
toggle, multiple threads, LaTeX, and select-text → **Ask** / **Rewrite** with
persistent highlights. The chat UI ships hidden in every post and only lights up when
the companion server is running.

It's **one server for all your posts**, set up once. Every post is built into a central
store (`~/.paper2blogpost/posts/`) that the server serves by default, and assembly makes
each post chat-ready automatically (grounding text and all) — so there's nothing to do
per post. Install the login agent once and from then on every post just works: open the
landing page, pick one, chat. Setup spends **no tokens**; only actually chatting does.

```bash
# one-time: auto-start the server at login (macOS), then browse your posts
python ~/.claude/skills/paper2blogpost/scripts/chat-server.py --install
open http://127.0.0.1:8877/         # landing page lists every post; click one → "💬 Ask Claude"
```

> Prefer not to install anything? Run it in the foreground instead:
> `python …/chat-server.py --dir ~/.paper2blogpost/posts` (or `--dir <single-post>`).
> Remove the login agent anytime with `--uninstall`.

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
