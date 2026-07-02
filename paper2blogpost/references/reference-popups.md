# Reference popups (lazy, on-demand)

When a reader hovers a citation, a small card shows the bibliographic line and a
**"What is it about?"** button. Clicking it generates a colloquial summary *right
then* with Claude Haiku and caches it in the reader's browser, so it's instant
every time after. You do **not** pre-write summaries at build time.

## Why lazy instead of pre-generated

A paper can cite 60–100 works. Summarizing all of them up front is slow, burns
tokens on references almost no one clicks, and tempts hallucination on obscure
citations. Generating one only when a reader actually asks is cheaper, faster to
build, and means a summary is produced with the reader's attention on it. The
trade is that summaries need a live model call — handled in the browser, below.

## What you produce: the citation data + the title

`build/refs.json`, keyed by `ref-N`, each entry has `num`, `citation`, and `title`:

```json
{
  "ref-1": {"num": 1, "citation": "Vaswani, A., et al. (2017). Attention Is All You Need. NeurIPS.", "title": "Attention Is All You Need"},
  "ref-2": {"num": 2, "citation": "Devlin, J., et al. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. NAACL.", "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"}
}
```

`title` is the cited work's title **copied verbatim from the citation** (an exact
substring — same words, punctuation, capitalization). The post uses it to **bold the
title** inside the bibliography and the hover popup, which makes a long reference list
far easier to skim. Bibliographies mix author formats ("J. P. Jones…" vs "Jones, J.
P.…"), so a regex can't reliably find the title — but you're reading each entry anyway,
so just pull the title out as you go. If a particular entry has no clear title, omit
the field (it simply won't bold).

No `summary` field. (If you ever *want* a particular reference to ship with a
ready-made summary — say the one the whole paper hinges on — you may add an
optional `"summary"` and `"relevance"`; the popup will show those directly and
skip the live call. Use this rarely; the default is lazy.)

## How the live generation works (already built into the template)

The reader clicks "What is it about?". The page splits the popup into two parts that
are cached **separately**, because they have different lifetimes:

- **SUMMARY ("what is it about")** — a property of the *reference*, identical wherever
  it's cited. Cached **per reference** (`p2b-sum:<paper>:<ref-id>`), so it's generated
  **once** and reused at every citation site.
- **RELEVANCE ("why it's here")** — specific to *this* citation. Cached **per site**
  (`p2b-rel:<paper>:<ref-id>:<hash-of-the-surrounding-passage>`), so each spot gets its
  own note.

So when the reader clicks:
1. if the reference's summary is already cached (a pre-seed in `refs.json`, or one this
   browser generated before), it shows **instantly** — even at a citation site never
   opened before — and the site-specific "Why it's here" fills in beside it as a bonus;
2. generating that note needs no web search (the work is already known), so it's a
   cheap, fast follow-up call; if there's no API key or it fails, the popup just shows
   the summary alone (the note is optional, never a blocker);
3. only the **first** time a reference is opened does the page do the expensive part: it
   asks for the reader's key if needed, then calls Claude Haiku from the browser **with
   the `web_search` tool enabled** — look the work up, summarize what it finds — and
   caches the summary (per reference) plus that first "Why it's here" (per site).

The summary is deliberately **very short and very casual** — one or two breezy
sentences, no jargon. The point of the split: a work cited ten times is summarized once
(one web search, not ten), but still gets ten location-specific notes.

**Why web search matters here.** Haiku summarizing a specific citation from memory
alone is unreliable — for an obscure or recent work it will (rightly) refuse rather
than fabricate, which gives the reader a useless "I don't know this paper" reply.
Grounding the call in a live web search fixes that: the summary is built from what's
actually out there, so it's accurate across the whole bibliography, not just famous
papers. The cost is a couple of web searches on the reader's key per click —
cheap, and only when they actually ask. The tool version is `web_search_20250305`
(the variant that works on Haiku).

All of that lives in `assets/template.html`. As the author of the post you don't
implement any of it — you just provide faithful `citation` lines (title + authors
intact, so the search has something to match) and make sure `{{PAPER_DATA}}` ends up
populated (the assembler does that from `meta.json`'s title, which Haiku uses as the
"why does this paper cite it?" context).
