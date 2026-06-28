# paper2blogpost — roadmap

Running log of what's shipped and what's queued, so requested features don't get lost.

## Shipped

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

**Phase 3 — polish (next).** Nicer thread switcher, delete-thread, multiple highlights per
passage, an "apply this rewrite to the post" action.

### 2. (more features to come)
