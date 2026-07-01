---
name: paper2blogpost
description: Turn a scientific paper PDF into a warm, colloquial, beautifully designed HTML blog post that keeps every bit of the actual content — it rewrites the stiff academic *language* into natural conversational prose without dropping any depth, figures, math, or references. Use this whenever someone wants a paper's writing made less stiff and more human while staying complete — e.g. "turn this arXiv PDF into a blog post," "rewrite this paper in plain, colloquial English as a webpage," "make this article read less stiff / less formal," "I want a nice friendly version of this study," or hands you a paper and asks for a casual / human / conversational walkthrough. Trigger even if they don't say the words "blog post" but clearly want a dense paper's prose transformed into a pleasant reading experience with the figures and references intact. This is about register, not reading level — not summarizing or simplifying-for-laypeople. Do NOT use for plain text extraction, content-dropping summaries, or slide decks.
---

# Paper → friendly blog post

## What you're making

A stiff scientific PDF, turned into a webpage someone would actually enjoy
reading — colloquial, visually calm, easy to navigate — **without losing any of
the real content**. This isn't a summary. It's a faithful translation from
academic dialect into natural, conversational language. If saying something
casually takes more words than the terse original, that's fine; longer-but-clearer
beats shorter-but-stiff. The science stays; only the delivery changes.

**This is about register, not reading level.** You are not "simplifying for a
general audience" or dumbing anything down. A domain expert should enjoy this
version *more* than the original — same depth, same rigor, same technical
content, just phrased the way a sharp colleague would actually explain it over
coffee instead of the stilted passive-voice formality journals demand. Keep all
the jargon that carries real meaning (explain it in passing the first time);
what you're dissolving is the *stiffness* of the prose, not its substance.

Three promises that define quality here:

1. **Every figure appears, pixel-faithful.** Same image as the paper. Only the
   *caption* gets translated into friendly language.
2. **Every reference survives**, and becomes interactive: hover a citation and a
   card offers a "What is it about?" button that generates a plain-language
   summary on demand (via Claude Haiku, cached in the browser) — so the build
   never stalls summarizing 90 references most readers won't open.
3. **It's a pleasure to navigate** — a translucent table of contents, smooth
   scrolling, a reading-progress bar, light/dark, real rendered math, and live
   cross-references: hover "Figure 3" or "Eq. 1" to peek at the actual thing,
   click to jump to it.

### The deliverable

A self-contained folder you can open or send to anyone:

```
<paper-name>-blogpost/
├── index.html      the blog post (design + content + inlined citation data)
├── figures/        figure images, exactly as they appear in the paper
└── refs/           the citation data (refs.json), inspectable
```

**Use a build directory unique to this paper — never a bare `build/` in the
current directory.** Name it after the deliverable (e.g.
`<paper-name>-blogpost/build/` or `<slug>-build/`). This matters because a generic
`build/` is a collision waiting to happen: if two conversions ever run from the
same place, they silently clobber each other's `sections/`, figures, and
`meta.json`. Tie the build dir to the paper and that whole class of bug vanishes.
Produce `index.html` in the deliverable folder with `figures/` and `refs/`
alongside it.

## Setup: extract everything first

You'll need PyMuPDF (`pip install pymupdf` if it's missing). Pick a unique build
dir for this paper (call it `$BUILD`), then run both extractors into it:

```bash
BUILD="<paper-slug>-build"          # unique per paper, NOT a bare "build"
python scripts/extract_text.py    --pdf "<paper.pdf>" --out "$BUILD"
python scripts/extract_figures.py --pdf "<paper.pdf>" --out "$BUILD" --dpi 200
```

This gives you `$BUILD/text/full.txt` (cheap to read — work from this, don't
re-render PDF pages over and over), `$BUILD/structure.json` (a *suggested*
section/heading map and where the references start), and `$BUILD/figures/` with
the figure images plus `manifest.json` (id, label, original caption, page). Skim
the figure manifest and spot-check a couple of images against the PDF — if a
figure came out cropped or mislocalized, note it; you can re-run with `--debug`
to get full-page renders and crop manually. **Getting figures right is a hard
promise, so it's worth a real look, not a glance.**

## The workflow

### 1. Map the paper before translating a word

Read `structure.json` and skim `full.txt` to build the real section list — title,
authors, then Intro / Background / Methods / Results / Discussion / etc. (use the
paper's actual structure, not a generic template). Sanity-check the suggested
headings against the paper; heading detection is heuristic and sometimes grabs a
bold phrase or misses a section. Decide the section breakdown now, because the
next step depends on a clean list. Also locate the bibliography (everything from
`references_start` onward).

Write `$BUILD/meta.json` (title, friendly `hero_title`, an inviting one-sentence
`dek`, and `meta_html` crediting + linking the original authors). See
`references/authoring.md` for the exact shape. (The `title` also becomes the
context Haiku uses when generating reference summaries, so make it the real paper
title.)

### 2. Translate section by section — one at a time

**This is the core of the skill, and the order matters.** Don't try to translate
the whole paper in one pass. Go section by section: read *that* section's
original text, rewrite it colloquially and completely, write it to its own file
in `$BUILD/sections/` (`01-intro.html`, `02-methods.html`, …), then move to the
next.

Why this discipline matters: a paper is long, and translating it all at once
forces compression — later sections get rushed, details get dropped, citations
slip through the cracks, and the "no lost content" promise quietly breaks. Taking
one section at a time keeps each translation faithful and complete, lets you
place the right figures and citations exactly where they belong, and keeps the
whole thing reviewable. It also mirrors how a good explainer is actually
written — paragraph by paragraph, not in one breath.

For each section, following `references/authoring.md`:
- Rewrite into warm, plain language (voice guidance below). Keep **all** the
  content — every result, caveat, number, and nuance — just say it like a human.
- Preserve **every citation** as a `<a class="cite" data-ref="ref-N">` marker
  with the original numbering. When you finish the section, re-scan the original
  for citation tokens and confirm each one made it across.
- Drop in the figures this section discusses (next step), with friendly captions.
- Keep equations as real math: wrap display equations in
  `<div class="equation" id="eq-N">$$…$$</div>` and add a plain-language gloss.
- **Reproduce notation exactly — styling included.** Symbols are content, not
  formatting: keep the paper's exact glyphs, case, accents, sub/superscripts, and
  especially their **weight**. A **bold** symbol is a vector/matrix (`$\mathbf{x}$`,
  `$\boldsymbol{\theta}$`) and means something different from the plain scalar `$x$` —
  never flatten it. Same for `\mathbb{}`, `\mathcal{}`, `\hat{}`, `\bar{}`, `^\top`, etc.
  Wrap in-prose variables in `$…$` so their italic/bold actually renders. Colloquial
  wording around the math is great; *changed* math is a bug. See `references/authoring.md`.
- **Formal statements get theorem boxes.** A Definition / Theorem / Lemma / Proposition /
  Corollary / Proof / Remark / Example → a `<div class="thmbox <environment>" id="thm-N">`
  with a `<span class="thm-label">`. The class sets the colour (results = terracotta,
  foundations = teal, commentary = grey); proofs use `.proofbox` + a ∎. Reproduce the
  statement faithfully (it's formal content); gloss it colloquially *around* the box, not
  inside. See `references/authoring.md`.
- **Wire up cross-references.** When the text says "Figure 3", "Eq. 1", "Table 2",
  wrap that mention in `<a class="xref" data-target="figure-3">…</a>` so the reader
  can hover to preview it and click to jump. This is a big part of what makes the
  post navigable. See `references/authoring.md`.
- Use a "Key idea" callout at most once per section, only for a genuine takeaway.

### 3. Figures: same image, friendlier caption

For each figure from `$BUILD/figures/manifest.json`, emit a `<figure>` using the
extracted image (keep its `id`), placed near where the text first discusses it.
Keep the `Figure N` label; rewrite the caption colloquially — tell the reader what
they're actually looking at and why it matters, not just a restatement of the
axes. The image itself is never altered. Markup is in `references/authoring.md`.

**Tables are not figures.** The extractor flags them (`kind: "tables"`) but can't
crop them faithfully — they're typeset text, not drawings. Rebuild each table as a
clean HTML `<table>` inside `<div class="table-wrap" id="table-N">` from the
extracted text (selectable, responsive, crisp) and translate its caption like any
other. Only fall back to the cropped image if a table is too big or intricate to
retype reliably. See `references/authoring.md`.

### 4. References: keep every one, no summarizing up front

Two parts:

- **The bibliography.** Reproduce the full reference list, in original order, as
  `$BUILD/references_list.html` — every entry, faithfully, each `<li id="ref-N">`.
  Removing or trimming references is not acceptable; they're part of the record.
- **The citation data.** Write `$BUILD/refs.json` with `num`, `citation`, and
  `title` (the cited work's title, copied verbatim from the citation — used to bold
  it in the bibliography and popups) per reference. No summaries — those are
  generated lazily by Claude Haiku when a reader clicks "What is it about?", then
  cached in their browser. This is deliberate: don't spend the build summarizing 90
  works most readers never open, and don't risk hallucinating about obscure ones.
  Full rationale + schema in `references/reference-popups.md`. Copy `refs.json` into the deliverable's `refs/`
  folder too.

### 5. Assemble

Stitch everything into the template:

```bash
python scripts/assemble.py --build "$BUILD" \
  --template assets/template.html --out "$BUILD/index.html"
```

This fills the design template, derives the table of contents from your section
ids + headings, and inlines the citation data + paper title (the latter is what
the in-browser Haiku call uses as context). The whole design — translucent TOC,
progress bar, reference popups, cross-reference previews, dark mode, math — lives
in `assets/template.html`; see `references/design-notes.md` to tune it. **Tweak
the template centrally there, not by hand-editing a generated post.**

### 6. Preview and self-check

Open the assembled `index.html` and verify against the promises:
- **Figures:** every figure from the manifest is present and looks right (not
  cropped/garbled); captions read like a human wrote them.
- **References:** every citation resolves to a card; the bibliography is complete;
  clicking "What is it about?" either shows a cached summary or prompts for an API
  key then generates one (test once with a key if you have one).
- **Cross-references:** hovering a "Figure N"/"Eq. N"/"Table N" link previews the
  target; clicking scrolls to it.
- **Navigation:** TOC links scroll smoothly and highlight the active section;
  progress bar moves; dark mode works; equations render.
- **Content fidelity:** spot-check a section against the original — nothing
  important was dropped in the name of friendliness.

Fix what's off, then present the folder to the user.

### 7. (Optional) enable chat mode

The post can gain a collapsible **sidebar chat** that answers questions about the
paper, grounded in its full text and running locally through the reader's `claude`
CLI. It's a *powered mode*: the chat UI is already in every post but stays hidden
unless the companion server is running, so a plain/shared copy is unaffected.

There's **one** companion server for *all* the reader's posts — set up once, then
every post just works (no per-post launching, and no tokens spent on setup). To make
a post chat-ready: drop the paper's plain text into it for grounding, and put the post
under the server's posts root (default `~/paper-blogposts/`).

```bash
cp "$BUILD/text/full.txt" "<post>/chat/paper.md"        # grounding text
mkdir -p ~/paper-blogposts && cp -R "<post>" ~/paper-blogposts/   # so the server serves it

# one-time setup — auto-starts at login, serves every post under the root:
python scripts/chat-server.py --install [--model claude-haiku-4-5]
# then open http://127.0.0.1:8877/ , pick the post, click "💬 Ask Claude"
```

(For a quick one-off you can still point the server straight at a single post:
`python scripts/chat-server.py --dir "<post>"`.) Full details — multi-post routing,
per-post lazy grounding/sessions, the `--install` LaunchAgent — are in
`references/chat-mode.md`.

## Voice: colloquial but complete

You're translating from academic into human, not dumbing down. Keep every fact;
change the register. Concretely:

- Prefer plain verbs and short clauses. "We hypothesize that X modulates Y" →
  "We think X changes Y." Active voice, contractions, the occasional aside.
- Explain jargon the first time in-line, don't just drop it. Add intuition and
  analogies where they genuinely help a reader *get* it.
- Keep the numbers, the caveats, the "but only under condition Z." Friendliness
  never means hand-waving away the parts that make it science.
- Keep the notation exact — same symbols, same **boldface** (a bold `$\mathbf{x}$` is a
  vector, not the scalar `$x$`). You reword the prose, never the math.
- Don't add hype or editorialize beyond what the paper supports. Warm and honest,
  not breathless.

**Example.**
Original: "We observe a statistically significant improvement (p < 0.01) in
downstream accuracy, albeit with increased variance across seeds."
Friendly: "The accuracy genuinely went up — this wasn't noise (p < 0.01). The
catch: results bounced around more depending on the random seed, so it's less
consistent run-to-run."

Both say the same thing. One of them you'd read on a couch.

## Resources

- `scripts/extract_text.py` — text dump + suggested structure map.
- `scripts/extract_figures.py` — pixel-faithful figure extraction (region render).
- `scripts/assemble.py` — stitch sections + data into the template.
- `scripts/chat-server.py` — optional local companion server for chat mode.
- `assets/template.html` — the entire design (HTML + CSS + JS). Iterate here.
- `references/authoring.md` — exact HTML conventions for sections, figures,
  citations, equations, meta, references. Read before translating.
- `references/reference-popups.md` — refs.json schema + the lazy Haiku summary
  mechanism (why we don't pre-generate summaries).
- `references/design-notes.md` — design language, interactions, how to tune it.
- `references/chat-mode.md` — the optional local chat companion (server + sidebar).
