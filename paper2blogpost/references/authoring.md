# Authoring conventions

Exact HTML to emit while translating. The design template styles all of this for
you — your job is to produce clean, correct fragments. Read this once before you
start translating sections.

## Section fragments

One file per section, in `build/sections/`, named so they sort in reading order:
`01-intro.html`, `02-background.html`, `03-methods.html`, … Each file is a single
`<section>` with a stable `id` (the TOC and scroll-spy key off it) and an `<h2>`:

```html
<section id="how-it-works">
  <h2>How the model actually works</h2>
  <p>Plain, friendly prose here…</p>
</section>
```

Use `<h3>` for subsections. Keep ids short, lowercase, hyphenated, and unique.

## Citations — always numbered, never dropped

Every in-text citation becomes a clickable marker. **Always render it as a plain
bracketed number `[N]`, regardless of the paper's original citation style.** Even
when the source uses author-year ("(Smith et al., 2020)"), show `[N]`, not the
author-year token. Reason: a paragraph sprinkled with `[Tsao et al., 2006]` and
`[Walker et al., 2019]` is visually noisy and reads inconsistently; bare numbers
keep the prose clean, and the hover popup + bibliography carry the detail.

`N` is the reference's position in the bibliography — assign sequential numbers in
order of first appearance and keep `refs.json` `num`, the `<li>` order in
`references_list.html`, and the in-text `[N]` all consistent.

```html
…as shown in earlier work <a class="cite" data-ref="ref-12">[12]</a>.
…and digital twins predict neural responses well
<a class="cite" data-ref="ref-9">[9]</a><a class="cite" data-ref="ref-10">[10]</a>.
```

Adjacent citations are just adjacent markers (`[9][10]`); don't merge them. The
`data-ref` must match a key in `refs.json`. Citations are the soul of this
format — losing one is the worst failure mode, so when you finish a section,
re-scan the original for citation tokens and confirm each one survived as a `[N]`.

## Figures — same image, friendlier caption

Use the extracted image and the figure's `id` from `figures/manifest.json`. Keep
the figure label, but rewrite the caption colloquially — explain what the reader
is actually looking at and why it matters, not just restate the axes:

```html
<figure id="figure-2">
  <img src="figures/figure-2.png" alt="Figure 2: accuracy vs. model size">
  <figcaption>
    <span class="figlabel">Figure 2</span>
    Bigger models keep getting better here — accuracy climbs steadily as the
    model grows, with no sign of flattening out yet. (Original caption:
    performance scaling with parameter count across three benchmarks.)
  </figcaption>
</figure>
```

Place each figure near where the text first discusses it. Don't alter, crop, or
recolor the image itself — fidelity to the original figure is a hard promise.

## Tables — rebuild them as real HTML, don't screenshot

A table is typeset text, not a drawing, so the figure extractor can't crop it
faithfully (it'll grab a blurry, lopsided band). It's also the one place where a
screenshot is strictly worse than the real thing: a rebuilt HTML table is
selectable, responsive, themeable, and renders crisply. The numbers are right
there in `full.txt` — transcribe them into a clean table and translate its
caption like any other:

Give the wrapper a stable `id="table-N"` so in-text mentions can link to it (see
Cross-references below):

```html
<div class="table-wrap" id="table-1">
  <table>
    <thead><tr><th>Model</th><th>BLEU</th><th>Training cost (FLOPs)</th></tr></thead>
    <tbody>
      <tr><td>Our base model</td><td>27.3</td><td>3.3×10¹⁸</td></tr>
      <tr><td>Our big model</td><td>28.4</td><td>2.3×10¹⁹</td></tr>
    </tbody>
  </table>
  <div class="table-cap"><span class="figlabel">Table 1</span>
    The big model wins on translation quality (higher BLEU) but costs far more to
    train — the usual quality-for-compute trade.</div>
</div>
```

Transcribe carefully — getting a number wrong silently corrupts the science. If a
table is genuinely too large or complex to retype reliably, fall back to the
extracted image (`<figure>`), but prefer the rebuilt table whenever it's feasible.

## Equations — keep the real math

Wrap inline math in `$…$`. Wrap each *display* equation in a `<div class="equation"
id="eq-N">` so MathJax renders it AND it becomes a jump target for in-text
mentions. Don't turn equations into prose or screenshots — a reader who wants the
math should get the math. You can *add* a plain-language gloss alongside it:

```html
<p>The loss is just the average surprise across the dataset:</p>
<div class="equation" id="eq-1">$$ \mathcal{L} = -\frac{1}{N}\sum_{i=1}^{N} \log p_\theta(x_i) $$</div>
<p>In words: how badly the model predicted each example, averaged over all of them.</p>
```

## Notation — reproduce it *exactly*, styling included

**Notation is content, not formatting.** The register changes; the symbols never do.
Reproduce every symbol the way the paper writes it — the same letters, the same case,
the same accents, and the *same weight and style*. Getting this subtly wrong quietly
corrupts the math, and a careful reader will notice immediately.

The one that gets dropped most often is **boldface**, and it's the one that matters
most: in almost every paper a **bold** symbol is a vector, matrix, or tensor, while the
same letter in plain italic is a scalar. `$\mathbf{x}$` (a vector) and `$x$` (one of its
components) are *different objects* — flattening the bold away is a real error, not a
cosmetic one. So:

- **Bold math stays bold.** Bold Latin letters → `\mathbf{x}`, `\mathbf{W}`; bold Greek →
  `\boldsymbol{\theta}`, `\boldsymbol{\mu}`. A bolded operator or word in running prose →
  wrap it in `<strong>`. Never demote a bold symbol to a plain one (or vice-versa).
- **Every other style is load-bearing too**, so keep it: blackboard-bold sets
  (`\mathbb{R}`, `\mathbb{E}`), calligraphic (`\mathcal{L}`, `\mathcal{N}`), Roman/upright
  for named operators and units (`\mathrm{softmax}`, `\mathrm{d}x`), sans-serif, Fraktur.
- **Accents, sub/superscripts, primes, stars:** `\hat{y}`, `\bar{x}`, `\tilde{p}`,
  `\dot{x}`, `x_i^{(t)}`, `\theta'`, `W^\top`, `A^{*}`. Copy them across verbatim.
- **Use the paper's exact glyphs.** If it writes $\theta$ don't switch to $w$; if it uses
  $\odot$ for elementwise product or $\langle\cdot,\cdot\rangle$ for an inner product,
  keep that symbol — don't paraphrase notation into words or "normalize" it to something
  you'd have picked.
- **Symbols in prose are still math.** When you mention a variable mid-sentence, wrap it in
  `$…$` (e.g. "each token $x_i$ is projected by $\mathbf{W}_q$") so the italic/bold renders
  correctly — don't type a bare letter, which loses the styling and looks like ordinary text.

When unsure, mirror the source glyph-for-glyph and weight-for-weight. Colloquial phrasing
around the math is encouraged; altered math is not.

## Formal statements — Definition / Theorem / Proof boxes

Math papers are full of formal environments — Definition, Theorem, Lemma, Proposition,
Corollary, Proof, Remark, Example… Give each its own **theorem box** so they stand out and
stay scannable (and so a "by Theorem 2.1" mention can hover-preview and jump to it). The
template styles them as a colored left rule + a bold label; the *class* picks the colour.

```html
<div class="thmbox theorem" id="thm-2-1">
  <span class="thm-label">Theorem 2.1 <span class="thm-name">(Soundness)</span></span>
  <p>Every causal model admits a unique minimal abstraction $\tau$ that preserves all
  interventions.</p>
</div>
```

- **The class after `thmbox` is the environment**, and it sets the colour automatically:
  - *results* → terracotta: `theorem`, `lemma`, `proposition`, `corollary`, `claim`,
    `conjecture`, `fact`
  - *foundations* → teal: `definition`, `assumption`
  - *commentary* → muted grey: `remark`, `example`, `note`, `observation`
- **Number it as the paper does** (`Theorem 2.1`) and give it an `id` (`thm-2-1`, `def-1-3`,
  …) so `<a class="xref" data-target="thm-2-1">Theorem 2.1</a>` mentions hover + jump to it.
- The optional `<span class="thm-name">(Soundness)</span>` holds the named title some
  statements carry.
- **The statement is formal content — reproduce it faithfully, notation and all** (see the
  notation rules above). Add a colloquial gloss *around* it if it helps ("in plain terms,
  …"), but don't reword the statement itself — same discipline as equations.

Proofs get a lighter treatment — a run-in *Proof.* and a ∎ to close:

```html
<div class="proofbox">
  <p><span class="proof-label">Proof.</span> By induction on the depth of the causal DAG;
  the base case is immediate. <span class="qed">∎</span></p>
</div>
```

## Cross-references — make "see Figure 3" come alive

A scientific paper is a web of "as shown in Figure 2", "(Eq. 1)", "see Table 3".
In the blog post, wrap each such in-text mention in an `<a class="xref">` pointing
at the element's id. On hover the reader gets a little preview of the actual
figure / equation / table; clicking jumps them to it. This is what makes the post
*navigable* instead of a wall you scroll blindly:

```html
…the full pipeline is laid out in <a class="xref" data-target="figure-1">Figure 1</a>,
and the scoring rule is just <a class="xref" data-target="eq-1">Equation 1</a>.
…performance numbers are in <a class="xref" data-target="table-1">Table 1</a>.
```

The `data-target` must match the `id` of a `<figure>`, a `<div class="equation">`,
or a `<div class="table-wrap">` somewhere in the post. Only wrap genuine
references to a specific numbered object — don't turn every word into a link.

## "Key idea" callouts (use sparingly, where they earn their place)

When a section turns on one core intuition, lift it into a callout so it lands:

```html
<div class="callout">
  <span class="callout-label">Key idea</span>
  Attention lets every word look at every other word and decide which ones matter
  — that's the whole trick behind transformers.
</div>
```

Don't overuse these; one per major section at most, and only when there's a
genuinely quotable takeaway. Too many callouts and they stop meaning anything.

## meta.json

```json
{
  "title": "Plain title for the browser tab",
  "hero_title": "The friendly headline readers see",
  "dek": "One inviting sentence that says what the paper found, in human terms.",
  "meta_html": "Original: <a href='https://arxiv.org/abs/...'>Authors, *Title*, Venue Year</a>"
}
```

`hero_title` may be a friendlier rephrasing of the paper's title; `meta_html`
must credit the original authors and link to the source so attribution is clear.

## References list + popup data

`references_list.html` is the full bibliography, in original order, each entry an
`<li>` with a matching `id`:

```html
<ol>
  <li id="ref-1">Vaswani, A., et al. (2017). Attention Is All You Need. NeurIPS.</li>
  <li id="ref-2">…</li>
</ol>
```

`refs.json` holds the popup data, keyed by the same ids. **You do NOT write
summaries here** — each entry is just the number and the citation line:

```json
{
  "ref-1": {"num": 1, "citation": "Vaswani, A., et al. (2017). Attention Is All You Need. NeurIPS."},
  "ref-2": {"num": 2, "citation": "…"}
}
```

The colloquial summary is generated *on demand* by Claude Haiku when a reader
clicks "What is it about?", then cached in their browser — so you never spend time
(or risk hallucinating) summarizing 90 references most readers will never open.
See `reference-popups.md` for the full rationale. Your job for references is just:
keep every one, number it, and copy its citation line faithfully.
