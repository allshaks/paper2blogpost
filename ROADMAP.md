# paper2blogpost — roadmap

Running log of what's shipped and what's queued, so requested features don't get lost.

## Shipped

- **Reference summaries cached per-reference, not per-citation** (2026-07-02): "What is
  it about?" used to key its *whole* cached blob (summary + relevance) by the citation's
  surrounding passage — so the same work cited in N places re-ran the full web-search
  summary N times. Split the cache: the **summary** ("what is it about") is keyed **per
  reference** and reused everywhere (generated once); only the **relevance** ("why it's
  here") stays keyed **per citation site**. A known reference cited again shows its summary
  instantly and generates just the location note via a cheap **no-web-search** call
  (`generateRelevance`); with no key or on error it degrades to summary-only (the note is
  never a blocker). Verified in-browser: two different citation sites of a 10×-cited ref
  reuse one summary with no re-prompt, and the note fails gracefully to summary-only.
  (`references/reference-popups.md` updated.)
- **CLAUDE.md "auto-generated" banner** (2026-07-02): the per-post `chat/CLAUDE.md` (the
  derived grounding doc = GUIDE + `paper.md`, rebuilt on every server start) now leads with
  an HTML-comment banner saying it's auto-generated and to edit `paper.md` instead — so a
  curious person browsing the `chat/` folder sees the source/derived relationship. (The
  duplication with `paper.md` is deliberate: a tool-less `claude -p` can't read `paper.md`,
  so the text must live in the auto-loaded `CLAUDE.md`; `paper.md` is the stable source, the
  server-owned `CLAUDE.md` is a regenerable cache that lets the GUIDE evolve across posts.)
- **Menu redesign + back-link, chat-message LaTeX, TOC reclaims space** (2026-07-02):
  three reading/navigation polishes. (1) The server's **landing page** was redesigned from
  a plain list into a warm menu that matches the posts (serif header, cards with each
  post's title + dek + a "Summary" badge for concise posts, hover arrows, light/dark) —
  `chat-server.py` now extracts title/dek/mode via `_meta_of`; each post also gained a
  **"← Posts"** link (in the top-right controls, shown only when served via `body.chat-on`)
  to jump back to that menu. (2) **The reader's own chat messages now render LaTeX**
  (`$…$` / `$$…$$`), not just the replies — the math-protection was factored into a shared
  `protectMath()`, replies use `mdLite` (markdown+math) and user messages a new `mdMath`
  (math only, so literally-typed text isn't markdown-mangled). (3) **Collapsing the TOC now
  hands its space to the reading column** — `body.toc-collapsed main` widens from
  `--maxw` (720) to `--maxw-wide` (864), and the chat-squeeze left guard drops to 0 when
  the TOC is hidden (no sidebar to clear). Verified in-browser (light+dark, 1200px):
  redesigned menu, back-link (`href="/"`), user-bubble math (block + inline, white on
  teal), and the column measurably widening 720→864 on collapse.
- **Click an equation → ask/define it** (2026-07-02): rendered MathJax is an unselectable
  SVG, so instead of fighting selection, a **click** on any display `<div class="equation">`
  opens the select-bubble (Ask + Define; "Rewrite" hidden — meaningless for math). It hands
  Claude the equation's **exact LaTeX**, not a lossy scrape: each equation's source is
  snapshotted into `data-tex` *before* MathJax swaps it for the SVG (synchronously, since
  MathJax loads later). An Ask thread seeds with the equation shown rendered + an
  "Equation N · Jump ↗" backlink, and on send marks the equation with the same teal
  highlight as a passage (reopen-on-click, hover-summary all work — the highlight classes
  were generalized from `mark.q-highlight` to `.q-highlight` so a block element can carry
  them, anchored by the equation's `id`); Define tags it terracotta. Only active when the
  chat server is live (a "💬 ask" hint shows on hover; `body.chat-on`); plain copies stay
  static. Display equations only (inline `$x_i$` deferred). Verified end-to-end against the
  live server: `data-tex` captures exact LaTeX (boldface `\mathbf{x}_i` preserved), bubble
  shows Ask+Define only, Ask opens a thread with the rendered equation + backlink + an
  "Ask about this equation…" placeholder, the block highlight renders (teal tint + underline).
- **Chat-ready by default** (2026-07-02): `assemble.py` now auto-writes the chat grounding
  text (`build/text/full.txt` → `<post>/chat/paper.md`, always the *full* paper even for a
  concise summary) as part of assembly. Combined with the central store, a post is
  chat-ready the instant it's built — step 7 collapsed from "copy + ground + install" to a
  one-time server `--install`, nothing per post.
- **Central post store + convenience symlink** (2026-07-02): every post is now built
  into one fixed store, `~/.paper2blogpost/posts/<slug>-blogpost/`, instead of landing
  wherever the skill happened to run. That store *is* the chat server's default `--dir`,
  so a post is "born" where the server already looks — the old "copy the finished post
  into `~/paper-blogposts/`" step is gone. A best-effort symlink (`scripts/publish.py`)
  is dropped in the working dir (`./<slug>-blogpost` → the central copy) so you can still
  open it from where you were; the symlink is never load-bearing (figures, chat,
  assembly, `--upgrade` all run off the real path), and on a system that can't symlink
  (e.g. Windows w/o Developer Mode) it degrades to a small HTML redirect + a printed
  path. If the working dir is a git repo, the pointer name is added to `.gitignore` (it
  targets an absolute `$HOME` path, so it shouldn't be committed). Name collisions in the
  store are surfaced to the user (overwrite / rename / cancel) rather than silently
  clobbering. `assemble.py` now `mkdir`s its `--out` parent so it can write anywhere.
  **Migration:** the default root moved from `~/paper-blogposts` → `~/.paper2blogpost/posts`;
  an existing post under the old root must be `mv`d over, and the LaunchAgent re-installed
  (`chat-server.py --install`) to pick up the new `--dir`. Verified end-to-end: assemble
  into the store, figures/refs materialized beside `index.html`, symlink published +
  idempotent + non-clobbering + git-ignored, figures resolve through the symlink, and the
  Windows fallback path.
- **Concise ("summary") mode** (2026-07-02): a second kind of post from the same
  pipeline — a short, colloquial, LessWrong-style *summary* (roughly a quarter to a
  third the length) instead of a complete translation, for when you want the gist
  without reading the whole paper. Same extraction, HTML conventions, assembly, and
  *all* the interactive features (reference popups, cross-refs, Define, sidebar chat) —
  the difference is purely editorial: keep the core narrative, key results with their
  numbers, the two or three figures that carry the story, and the load-bearing
  equations (notation still exact); cite fewer works inline but keep the *full*
  bibliography; open with a **TL;DR key-takeaways box**. A **"Summary" badge** + *"The
  short version"* eyebrow mark the hero, driven by a `body.concise` class the assembler
  adds (`--mode concise`, or `"mode":"concise"` in `meta.json`; `--upgrade` preserves
  it). Chat grounding stays the *full* paper text, so a reader of the summary can still
  ask the sidebar for the detail it left out. New `references/concise.md` (the deltas);
  `SKILL.md` gained a mode-selection step + an updated `description` that now triggers
  on "summarize this paper as a blog post" / "short / TL;DR / LessWrong-style version."
  Verified in-browser (light + dark): badge, eyebrow swap, TL;DR box, TOC excludes the
  TL;DR, inline math + citations still render; full/concise/meta-mode/upgrade round-trips
  all fill the body class correctly and idempotently.
- **LaTeX in every popup** (2026-07-01): all content popups now typeset `$…$` / `$$…$$` with
  MathJax, not just the Define one — the reference "What is it about?" summary (`#refpop`),
  cross-reference previews (`#xpop`), the definition popup (`#defpop`), and the chat-highlight
  summary (`#threadpop`). Shared `mjTypeset()` helper; summaries render via the math-aware
  `mdLite` path. Verified each popup renders an injected formula.
- **Chat-highlight hover summary** (2026-07-01): hovering a passage highlight shows a small
  popup with a one-line informal summary of that chat thread, plus a "Bottom line:" sentence
  if it reached a conclusion. Generated by Haiku and cached per thread (regenerated only when
  the message count changes); `GET …/__chat/summary/{tid}` + `Ctx.summarize_thread`.
- **Define dedup** (2026-07-01): before calling the LLM, `_define` checks whether the term was
  already defined — folding case, spaces, newlines, hyphens, and underscores (`_norm_term`) —
  and if so reuses that definition for the new selection instantly (`reused: true`, no call).
- **Collapsible table of contents** (2026-07-01): a `«` in the TOC hides it (slides off-screen
  + fades); a floating `☰ Contents` button brings it back. State remembered in localStorage;
  hidden on mobile as before.
- **LaTeX in Define popups** (2026-07-01): the Define lookup now emits LaTeX for formulas
  (`$…$` / `$$…$$`), and the definition popup renders it with MathJax (same math-aware
  `mdLite` + `typesetMath` path as the chat, re-placing after typeset). The server also
  repairs the common invalid-JSON case where the model leaves LaTeX backslashes unescaped
  (try raw parse → retry with lone backslashes doubled). Verified: defining "cosine
  similarity" renders its formula in the popup.
- **Footnote styling** (2026-07-01): the model already emits blog-style footnotes (a `<sup>`
  xref marker + a `<p class="footnote">` note near its reference), but the template never
  styled them, so they rendered at body size. Added `.footnote` (smaller, muted, left rule) +
  a shrunk `<sup>` marker, a "Footnote" hover-preview label, and authoring conventions.
  Because the markup already exists in posts, an existing post gets this fixed by `--upgrade`
  alone (no re-translation needed).
- **Theorem-environment boxes** (2026-07-01): first-class Definition / Theorem / Lemma /
  Proposition / Corollary / Proof / Remark / Example / Assumption / Claim / Conjecture boxes
  in the template — a colored left rule + bold label (style "C"), colour by family (terracotta
  = results, teal = foundations, grey = commentary), proofs with a ∎. They're cross-reference
  targets too (hover "Theorem 2.1" → preview, click → jump). Authoring conventions in
  `SKILL.md` + `authoring.md`. Replaces the old failure mode where a math paper's boxes were
  ad-hoc per-post CSS that vanished on any re-generation/upgrade. (Applies to *new* posts;
  an existing post needs re-translating to wrap its statements in the boxes.)
- **Exact-notation fidelity** (2026-07-01): the skill now explicitly insists that notation is
  *content, not formatting* — same glyphs, case, accents, sub/superscripts, and **weight**. A
  bold `$\mathbf{x}$` (vector/matrix) must never be flattened to the scalar `$x$`. Guidance
  added to `SKILL.md` (translate step + voice) and a full `references/authoring.md` subsection
  (`\mathbf`/`\boldsymbol`/`<strong>`, `\mathbb`/`\mathcal`/`\mathrm`, accents, `^\top`, wrap
  in-prose variables in `$…$`). Guides future runs; won't retro-fix already-flattened posts.
- **`assemble.py --upgrade`** (2026-07-01): re-skins an *already-assembled* post to the current
  template with no `build/` dir — extracts the filled content (TOC, hero, article, references,
  `__REFS__`/`__PAPER__`) off stable structural anchors, re-stitches into the latest template,
  backs up `index.html` → `.bak`. Lets old posts pick up template features (e.g. Define) in
  place. Verified: round-trip is content-lossless and repeated upgrades are idempotent.
- **Section-by-section translation** into colloquial register (not summary, not dumbed-down).
- **Pixel-faithful figure extraction** (region-render; handles caption-above *and* caption-below layouts).
- **Tables rebuilt as real HTML** (not screenshots).
- **References kept in full**, with hover popups.
- **Lazy, web-search-grounded reference summaries** — "What is it about?" calls Claude Haiku *with the `web_search` tool* so summaries are accurate for obscure/recent works instead of refusing. Reader's own key, cached in `localStorage`.
- **Scrollable popups**; **cross-reference hover previews** (figures/eqs/tables, click-to-jump).
- **Unique build dir per run** (fixed a parallel-run race condition).
- **Numbered citations** — always `[N]`, never author-year tokens, for clean prose. (Done 2026-06-28.)
- Design: translucent scroll-spy TOC, reading progress bar, light/dark, MathJax.
- **Multi-panel / multi-page figures** (2026-06-28): the extractor now recognizes "(a)/(b)…"
  sub-captions and links orphaned panels to the current figure even across pages (recovered
  Figure 3b *and* Figure 2b in the neuro paper), and clips crops against sub-captions so no
  caption strip leaks into the image.
- **Resizable, page-squeezing chat** (2026-06-28): drag the left grip to set the
  sidebar width; remembered. Opening/widening it *squeezes the page left* (reserves
  right-side `body` padding) instead of covering the article — the reading column's
  width is held constant; only its margins recompute. A left guard keeps the column
  clear of the TOC and that same guard caps the chat's max width
  (`vw − guard − column − gutter`); narrow viewports fall back to overlay.
- **Clickable reference links** (2026-06-28): DOIs / arXiv ids / URLs in the bibliography and
  popups become links that open in a new tab; refs without one get a Scholar "find ↗" link.
- **Bold reference titles** (2026-06-28): refs.json gains a verbatim `title` field; the popup
  and bibliography bold the title so a long reference list is easy to skim. (Future runs: the
  model emits `title`. Existing post: titles extracted via a one-off `claude` batch, 89/92.)

## Planned

### 1. Local Claude chat woven into the post

Decisions (locked): **CLI subprocess** (`claude -p`, the reader's Claude Code login — no
API key) · **sidecar** `chat/threads.json` storage · **sidebar chat first**, highlights next.

**Phase 1 — sidebar chat — ✅ DONE (2026-06-28).** `scripts/chat-server.py` (binds
127.0.0.1) serves the post and bridges an in-page collapsible sidebar to `claude -p`.
Grounded in the paper via a `chat/CLAUDE.md`; streams token-by-token over SSE; each thread
maps to a resumable `claude` session id; threads persist to `chat/threads.json` (verified:
resume survives server restarts). Quiets the user's env selectively (no MCP, persona
override of output style) — not `--bare`, which would force an API key. Chat UI is in every
post but hidden unless the server answers `/__chat/ping`. See `references/chat-mode.md`.

**Phase 2 — ✅ DONE (2026-06-28).** Verified end-to-end in the browser:
- **Select-text bubble** → **Ask** (opens a thread seeded with the passage as context) or
  **Rewrite for clarity** (Claude returns a clearer version). Either wraps the selection in a
  `<mark class="q-highlight" data-thread="…">` that stays as a trace; clicking it reopens that
  exact thread. Highlights persist via a `{quote, sectionId, start, length}` anchor and are
  re-applied on load (verified across a full reload).
- **Model + effort pickers** and a **🌐 Web internet toggle** in the chat header (per-message;
  effort auto-dropped for Haiku; web = `--tools "WebSearch,WebFetch"`). Dropped the
  "grounded… runs locally" subtitle.
- **Multiple chats**: `＋` new chat, `☰` history of all threads in the paper (passage/rewrite
  badges), switch between them.
- Fixed an async load-race (highlight-click had loaded two threads into one list) with a load token.
- Fixed a stuck-Send bug: SSE `keep-alive` meant the client read loop never ended, so the
  re-enable `finally` never ran — now the client breaks on the `{done:true}` event + the server
  sends `Connection: close`. And deferred highlight creation to send-time (a passage is only
  marked once a message is actually sent, not on opening the bubble).
- **Live agent-activity status** (2026-06-28): a pill shows what the agent is doing in
  real time — 💭 Thinking · 🌐 Searching the web *"query"* · 📑 Reading the results · 📖
  Reading · ⌘ Running a command · … — instead of a bare spinner. The server reads
  `claude`'s `stream-json` (`content_block_start` for the earliest thinking/tool signal,
  the consolidated `assistant` turn to add the tool's input as detail, `user` tool-results
  to show it's digesting them) and forwards each as a `{phase, icon}` SSE event; the pill
  clears when answer tokens begin. Verified end-to-end against a real web-search run.
- **Contained chat scrolling** (2026-06-28): `overscroll-behavior:contain` on the message
  and thread lists, so reaching the chat's top/bottom no longer scroll-chains the article.
- **LaTeX math in chat** (2026-06-28): replies render with MathJax — inline `$…$` and
  displayed `$$…$$` (the persona instructs the model to emit real LaTeX). `mdLite` protects
  math spans from the markdown passes; `typesetMath()` typesets each finished message
  (streamed-on-done + restored-from-history). Verified both paths render in the browser.
- **Masked API-key dialog** (2026-06-28): the 🔑 Key control no longer uses a plaintext
  `prompt()` — it's a `type=password` modal with a 👁 reveal toggle (Save/Clear/Cancel,
  Enter/Esc). The inline reference-popup key form was already masked.
- **Restart-stable thread ordering** (2026-06-28): chat threads are now timestamped with
  wall-clock `time.time()` in `save_turn` (the old in-process counter reset to 0 on every
  restart, so "open most recent" could open an older thread). Verified: a touched thread
  gets a real Unix timestamp and sorts to the top. Removed the now-dead `_counter`.
- **Passage backlink in chat** (2026-06-28): a passage-anchored thread shows a backlink bar
  at the top of the chat (the quote + **Jump ↗**) that smooth-scrolls the article to the
  passage and flashes it. Shown both for new select→Ask/Rewrite threads and passage threads
  reopened from history. Verified: bar renders the quote; Jump centers + flashes the mark.
- **Define (select-text → 3-tier lookup)** (2026-07-01): the selection bubble gains
  **Define** alongside Ask/Rewrite. A fixed **Sonnet 5 / medium** call (internet on) tries,
  in order: define from the paper (with a `paper_quote` locator) → follow a nearby citation
  and define from that reference on the web (URL / `[N]`) → define from memory. The term gets
  a distinct **terracotta** highlight (vs the teal chat ones); hovering shows a popup with the
  definition + a source link (jump-to-it-in-the-paper via fuzzy match since the article is a
  rewrite, open-the-reference, or "from general knowledge"). Persists per-post in
  `chat/definitions.json`. New server endpoints `POST/GET …/__chat/define[initions]`; the chat
  streaming loop was extracted into a shared `_run(stream_text=…)`. Verified end-to-end:
  memory + paper tiers, terracotta highlight, hover/dismiss/re-show, reload persistence, and
  the fuzzy jump locating the definition in the colloquial text.
- **History “← Back to current chat”** (2026-06-28): the thread-list overlay (which covers
  the header) gains a back row so you can return to the chat you were in without having to
  pick one. Default chat model set to **Sonnet** (was already the code default; documented).
- **One persistent multi-post chat server** (2026-06-28): replaced the per-post server with
  a single always-on server that serves a whole folder of posts (landing page at `/` lists
  them; each at `/<post>/`), with **lazy per-post state** (each post's own `chat/paper.md`
  grounding + `chat/threads.json`, created on first use). `--install` writes a macOS
  LaunchAgent so it auto-starts at login → set up once, then any post just works. The client
  now uses **relative** `__chat/…` URLs so it works wherever a post is mounted. Removes the
  per-html launch friction; setup spends no tokens (only chatting does). Verified single- and
  multi-post modes, the index, per-post grounding isolation, 404s, and in-browser relative
  pings. (Clears up the user's worry about "wasting tokens to set up chat per html" — setup
  is pure file I/O.)

**Phase 3 — polish (next).** Nicer thread switcher, delete-thread, multiple highlights per
passage, an "apply this rewrite to the post" action.

### 2. (more features to come)
