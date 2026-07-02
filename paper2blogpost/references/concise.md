# Concise mode — the LessWrong-style summary post

Sometimes you don't want the whole paper — you want the *gist*: what they did, what
they found, why it matters, with the figures that carry the story, in ten minutes
instead of an hour. That's **concise mode**. It produces the same beautiful,
interactive post as the full translation, but *significantly summarized* — think a
good LessWrong writeup of a paper rather than a faithful line-by-line rendering.

**Everything about the pipeline is the same** — extract, map, translate section by
section, assemble, optional chat. The **HTML conventions in `authoring.md` are the
same** (sections, figures, citations, equations, theorem boxes, cross-references).
Every interactive feature still works: reference popups, cross-ref previews, Define,
the sidebar chat. What changes is purely *editorial*: how much you keep, and how
short you make it. This file is the delta from the full-mode workflow in `SKILL.md`.

## How you know it's a concise request

Default is **full**. Switch to concise when the user asks for a *summary* rather than
a translation: "summarize this paper as a blog post," "give me a short / TL;DR
version," "a LessWrong-style writeup," "just the gist as a nice webpage," or an
explicit "concise mode." When it's ambiguous, ask — the two produce very different
artifacts.

## Depth: a LessWrong digest

Aim for roughly **a quarter to a third** of a full translation. Follow the paper's
section structure, but each section becomes **a few tight paragraphs** carrying its
key points and the intuition behind them — not a paragraph-for-paragraph rewrite. You
may **merge minor sections** (e.g. fold a short "Preliminaries" into the intro) and
**drop purely structural ones** (detailed experimental setup, long related-work
surveys → a sentence or two). Keep the reading *colloquial and warm* — same voice as
full mode, just far more compressed.

The test: someone who reads only your summary should walk away understanding *what the
paper claims, the evidence for it, and why it's interesting* — without feeling they
were handed marketing. Depth over breadth: better to explain the one central idea well
than to name-check every result.

## What to keep, what to cut

**Keep:**
- The **core narrative and argument** — the problem, the key idea, the main result.
- The **headline results with their real numbers** (the ones that matter), and the
  honest caveat when a result is qualified. A summary that drops every caveat is a
  press release, not science.
- The **key figures** — the two or three that *carry the story*, with friendly
  captions (same figure markup and pixel-faithfulness as always). Skip the rest.
- The **load-bearing equations** only — the one or two a reader needs to get the idea,
  as real math (`<div class="equation">`). Reproduce **notation exactly**, boldface and
  all (see `authoring.md` — this rule never relaxes, even in a summary). Drop routine
  derivations.
- The **full bibliography.** Reproduce *every* reference in `references_list.html` and
  `refs.json` exactly as in full mode — the list is cheap and losing references is the
  worst failure mode. You just **cite fewer of them inline**: only wire `<a class="cite">`
  markers for the works the summary actually leans on. Uncited entries still live in the
  bibliography (and their hover popups still work).

**Cut or compress hard:**
- Exhaustive derivations, **proofs** (state the theorem in its box if it's central,
  skip the proof), step-by-step methods.
- Every ablation, secondary experiment, and hyperparameter table.
- Most **footnotes** (keep only one that's genuinely load-bearing).
- Long related-work and background sections → a sentence of context.
- Repetition, throat-clearing, and "as we will see in Section 6."

When you drop something, drop it **cleanly** — don't half-say it. A crisp omission
reads better than a mangled compression.

## The TL;DR box (concise mode's signature element)

Open the article with a **key-takeaways box** so a reader gets the whole point in ten
seconds. Write it as the very first content file, `sections/00-tldr.html`, as a bare
`<div class="tldr">` (no `<section>` wrapper, so it sits above the first section and
gets no TOC entry):

```html
<div class="tldr">
  <div class="tldr-label">TL;DR</div>
  <ul>
    <li>The one-sentence claim of the paper, in plain words.</li>
    <li>The key result, with the number that matters.</li>
    <li>Why it's interesting / what it changes.</li>
    <li>The main caveat or limitation, if there's an important one.</li>
  </ul>
</div>
```

Three or four bullets, each a full but tight sentence. The template styles `.tldr`
(accent-tinted, left-ruled) automatically. Label it `TL;DR` or `Key takeaways`.

## The Summary badge — automatic, don't author it

Concise posts wear a small **"Summary"** badge in the hero and a *"The short version"*
eyebrow instead of *"A friendly walk-through."* You don't write any of that — it's
driven by a `body.concise` class the assembler adds when you build in concise mode.

## Assembling a concise post

Same command as full mode plus `--mode concise` (which sets the body class → badge +
eyebrow):

```bash
python scripts/assemble.py --build "$BUILD" --out "$POST/index.html" --mode concise
```

Equivalently, set `"mode": "concise"` in `meta.json` and the assembler picks it up
without the flag. `--upgrade` preserves whichever mode a post was built in.

## Deliverable naming — let both coexist

Build a concise post into **`~/.paper2blogpost/posts/<paper-name>-summary/`** (vs.
`…-blogpost/` for a full translation) so both the short and the complete version of the
same paper can sit in the central store side by side.

## Chat grounding stays the *full* paper

When you enable chat on a concise post, still drop the **full** extracted text into
`<post>/chat/paper.md` (not your summary). That way the sidebar chat can answer in
depth about things the summary deliberately left out — the summary is the lens, the
whole paper is still underneath it. Everything else about chat mode is unchanged
(`chat-mode.md`).

## Self-check (in addition to the full-mode checks)

- **Is it actually short?** Skim it against the paper — a quarter to a third, not a
  lightly-trimmed full post. If a section still reads exhaustively, cut again.
- **Does the TL;DR stand alone?** A reader should get the paper's point from those
  bullets without scrolling further.
- **Right figures?** The ones you kept should be the ones that carry the argument, not
  just the first few.
- **Bibliography intact?** Every reference is still in the list, even though you cited
  fewer inline. Notation is still exact. Nothing you *did* keep was distorted to fit.
