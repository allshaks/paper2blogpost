# Design notes

The whole look-and-feel lives in `assets/template.html` (one file: HTML scaffold
+ inlined CSS + inlined JS). Iterate on the design *there* so every future post
inherits the change — never bake bespoke styling into a generated post.

## The feel we're going for

A stiff PDF turned into something you'd actually want to read on a Sunday: warm,
calm, unhurried. A comfortable serif body (Newsreader) for the reading itself, a
crisp sans (Inter) for UI and headings. Generous line-height. A single warm
accent (terracotta) and a cool one (teal) for links/citations — restraint, not a
rainbow.

## Interactions already built in

- **Translucent TOC** (left, fixed): sits at ~30% opacity and fades to full on
  hover, so it's present but never shouty. Highlights the current section via an
  IntersectionObserver scroll-spy.
- **Reading progress bar** along the top.
- **Reference popups (lazy)**: hover to peek, click to pin. "What is it about?"
  generates a colloquial summary on demand via Claude Haiku (reader's own API key,
  stored in `localStorage`, set via the 🔑 Key control or an inline form), then
  caches it. The Haiku call has the **`web_search` tool enabled** so it grounds the
  summary in a live lookup of the cited work instead of guessing from memory — this
  is what makes it accurate for obscure/recent citations rather than refusing. A
  `summary` pre-seeded in `refs.json` skips the live call. Popups are scrollable
  (`max-height` + `overflow-y`).
- **Cross-reference previews**: `a.xref[data-target]` links to a `<figure>`,
  `.equation`, or `.table-wrap` id — hover shows a live preview of that element,
  click smooth-scrolls to it and flashes it. Shares the placement/flip logic with
  reference popups.
- **Clickable references**: DOIs / arXiv ids / URLs in the bibliography and reference
  popups are auto-linkified (open in a new tab); a reference with none gets a Scholar
  "find ↗" link. Done on load by `linkifyCitation` — authors don't do anything.
- **Resizable, page-squeezing chat**: a left-edge grip (`#chat-grip`) drags the
  sidebar width; remembered. Opening or widening it doesn't *cover* the article — it
  **squeezes the page left** by reserving room on the right (`body.chat-squeeze`
  sets `padding-right:var(--chat-w)`). The reading column's own width never changes;
  only its margins recompute, so it slides over and re-centers. A left guard
  (`padding-left:var(--chat-guard)`) keeps that centered column clear of the TOC,
  and that same guard is exactly what **caps the chat's max width**
  (`max = viewport − guard − column − gutter`, computed in `chatGeom()`). On
  viewports too narrow to fit both (≈ < 1340px) it falls back to overlaying. The
  squeeze animates with the slide; transitions are killed mid-drag so resizing is
  instant.
- **Light/dark toggle**, remembered in `localStorage`.
- **Gentle section reveal** on scroll (respects `prefers-reduced-motion`).
- **MathJax** for equations.

The Haiku call is a direct browser `fetch` to `api.anthropic.com` with the
`anthropic-dangerous-direct-browser-access` header and the reader's key. Model id
lives in `HAIKU_MODEL` at the top of the popup script — bump it when newer Haiku
versions ship.

## Tuning knobs (CSS variables at the top of `:root`)

`--accent`, `--link`, `--bg`, `--maxw` (reading-column width), `--serif`,
`--sans`. Change these first before touching anything structural — most "make it
feel different" requests are a palette or typography change, not a rewrite.

## Things to be careful about

- The TOC hides under 1100px wide (no room). If you add features, keep mobile in
  mind — the reading column should stay usable on a phone.
- Popups are `position:fixed` and clamp to the viewport; if you restyle them,
  keep the clamping logic or they'll overflow on small screens.
- Web fonts load from Google Fonts; everything degrades to system fonts if
  offline. Don't make the design *depend* on the web fonts loading.
