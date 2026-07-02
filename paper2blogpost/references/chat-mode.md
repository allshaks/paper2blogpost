# Chat mode (local companion server)

The post can become something you *think with*: a collapsible sidebar chat that
answers questions about the paper, grounded in its full text. This is a **local
powered mode** — it lights up only when a small companion server is running next
to the post; a plain or shared copy stays a clean static read.

## How it fits together

- **`scripts/chat-server.py`** — **one** local server (binds `127.0.0.1` only) for
  *all* your posts; you set it up once. It:
  1. serves a folder of posts — by default the **central store**
     `~/.paper2blogpost/posts/` that the skill builds every post into; the landing page
     at `/` is a designed **menu** (warm cards with each post's title, dek, and a
     "Summary" badge for concise posts) and each post is served at `/<post-name>/` (it
     also accepts a single post folder directly). Every post carries a **"← Posts"** link
     (top-right controls, shown only when served) to get back to that menu, and
  2. bridges each post's in-page chat to the user's **`claude` CLI** (their Claude
     Code login — no API key). A thread maps to a resumable `claude` session id.
- **Per-post state, created lazily**: the first time a post is chatted with, the
  server writes `<post>/chat/CLAUDE.md` (a guide + that post's paper text from
  `<post>/chat/paper.md`) and reads/writes `<post>/chat/threads.json`. `claude` runs
  from `<post>/chat/`, so every turn is grounded in *that* paper (cached after the
  first call). **Setting this up costs no model tokens — only actually chatting does.**
- **Front-end**: the template's `#chat` sidebar pings `__chat/ping` — a **relative**
  URL, so it resolves to `/<post>/__chat/ping` wherever the post is mounted (and to a
  dead URL under `file://`, leaving plain copies static). If the server answers, the
  "💬 Ask Claude" launcher appears. Messages stream back token by token over SSE.

The server quiets the user's global Claude Code environment selectively — it loads
**no MCP servers** (`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`) and
appends a persona system prompt that overrides any injected output style (so you
don't get "★ Insight" blocks in a reader chat). It deliberately does **not** use
`--bare`, because that would force an API key and drop the CLAUDE.md grounding.

## What the skill must do at build time

**Nothing extra.** The post is built directly into the server's posts root (the central
store `~/.paper2blogpost/posts/<paper-slug>-blogpost/`), and `assemble.py` automatically
writes the grounding text to `<post>/chat/paper.md` (always the *full* paper text — even
for a concise summary post, so the chat can answer in depth about the parts the summary
left out). Everything else (`CLAUDE.md`, `threads.json`) the server creates itself,
lazily, in `<post>/chat/`. If `paper.md` is somehow absent the chat still works but
won't be grounded.

## Running it (tell the user)

**Recommended — set up once, runs forever.** Install a login agent (macOS) that keeps
the server up, so afterwards every post just works with nothing to launch:

```bash
python scripts/chat-server.py --install [--dir ~/.paper2blogpost/posts] [--model claude-haiku-4-5]
# auto-starts now and at every login; open http://127.0.0.1:8877/ and pick a post.
# remove later with:  python scripts/chat-server.py --uninstall
```

**Or just run it in the foreground** (a folder of posts, or one post):

```bash
python scripts/chat-server.py --dir <folder-of-posts | single-post> [--model …]
```

`--model` is the *default*; the reader can pick model + effort live in the chat header
(see below), which overrides it per message. `--install` writes a macOS LaunchAgent
(`~/Library/LaunchAgents/com.paper2blogpost.chat.plist`); on Linux, run the foreground
command from a `systemd --user` service or a login script instead.

## In the chat UI

- **Model + effort pickers** in the header (Haiku / Sonnet / Opus; low…max). Sent
  per message; effort is dropped automatically for Haiku (which rejects it). The
  default is **Sonnet** / medium (the last-used choice is remembered in localStorage).
- **🌐 Web toggle** — off runs a pure grounded chat (`--tools ""`, fast); on gives
  Claude `WebSearch`/`WebFetch` so it can look things up. Remembered in localStorage.
- **Multiple chats** — `＋` starts a new thread; `☰` lists every chat opened in this
  paper (with a `passage`/`rewrite` badge) to switch between them, and a **← Back to
  current chat** row returns you to the one you were in without picking another (the
  list overlay covers the header, so this is the way back out). Threads live in
  `chat/threads.json`, each mapped to a resumable `claude` session.
- **Select any passage** → a small bubble offers **Ask** (opens a thread seeded with
  that passage so your question has context) or **Rewrite for clarity** (Claude
  returns a clearer version of the passage). Either wraps the selection in a
  `<mark class="q-highlight" data-thread="…">` that *stays* as a visible trace;
  clicking it reopens that exact thread. Highlights persist via a text-offset
  `anchor` ({quote, sectionId, start, length}) stored on the thread and re-applied
  on load. A passage thread also shows a **backlink bar** at the top of the chat (the
  quote + **Jump ↗**) that smooth-scrolls the article to the passage and flashes it —
  so you can always get from the conversation back to the spot it's about.
  **Hovering** a highlight pops a one-line informal summary of that thread (+ a "Bottom
  line:" sentence if it reached a conclusion) — Haiku-generated, cached per thread via
  `GET …/__chat/summary/{tid}`.
- **Live activity status** — while the agent works, a pill shows what it's doing
  right now (💭 Thinking · 🌐 Searching the web *"query"* · 📑 Reading the results ·
  📖 Reading · ⌘ Running a command · …), not just a spinner. The server taps
  `claude`'s `stream-json` events — `content_block_start` for the earliest signal of
  a thinking/tool block, the consolidated `assistant` turn to refine the pill with
  the tool's actual input (the search query, the file), and `user` tool-results to
  show it's reading what came back — and forwards each as a `{"phase","icon"}` SSE
  event. The pill clears the moment answer tokens start streaming. To add a label,
  extend `TOOL_PHASES` / `_tool_detail` in `chat-server.py`.
- **Contained scrolling** — the message list and thread list use
  `overscroll-behavior:contain`, so scrolling the chat to its top/bottom never
  spills over into scrolling the article underneath.
- **Define** — the select-text bubble also offers **Define**. It runs a fixed
  **Sonnet 5 / medium** lookup (internet on) with a strict 3-tier strategy: (1) find a
  definition *in the paper* (returns a `paper_quote` to locate it); (2) else follow a
  nearby **citation** and define from that reference on the web (returns its URL / `[N]`);
  (3) else define *from memory*. The selection gets its own **terracotta** highlight
  (distinct from the teal chat ones), and hovering it shows a popup with the definition
  and a source link — **jump to it** in the paper (fuzzy-matched, since the article is a
  rewrite so the original phrasing rarely survives verbatim), **open** the external
  reference, or a note that it's from general knowledge. Definitions persist per-post in
  `chat/definitions.json` and re-apply on load. **Dedup**: before the LLM call, `_define`
  folds the term (case / spaces / newlines / hyphens / underscores) and reuses an existing
  definition if the same term was already defined — instant, no call. The definition text
  is LaTeX-aware: formulas render with MathJax in the popup (server repairs unescaped-
  backslash JSON). Server: `POST …/__chat/define` (SSE, same phase pills as chat) +
  `GET …/__chat/definitions`.
- **Click a display equation → Ask / Define it** — rendered math is an unselectable SVG,
  so instead of trying to select it, a **click** on any `<div class="equation">` opens the
  same bubble (Ask + Define; no "Rewrite" — meaningless for math). It hands Claude the
  equation's **exact LaTeX**, not a lossy text scrape: each equation's source is snapshotted
  into `data-tex` *before* MathJax swaps it for the SVG. An Ask thread seeds with the
  equation (shown rendered, with an "Equation N · Jump ↗" backlink) and, once you send,
  marks the equation with the same teal highlight as a passage (reopen on click, hover for
  the thread summary); Define tags it terracotta and explains it in the popup. Only lit up
  when the server is live (a small "💬 ask" hint appears on hover); a plain copy stays a
  static read. Display equations only for now — inline `$x_i$` symbols aren't clickable yet.
- **LaTeX math** — **both your own messages and the replies** render math with the
  page's MathJax: inline `$…$` and displayed `$$…$$` (the persona tells the model to emit
  real LaTeX). A shared `protectMath()` pulls math spans out before any markdown pass so
  `*`/`_` inside an equation aren't mangled; replies go through `mdLite` (markdown + math),
  your messages through `mdMath` (math only — text you typed literally isn't
  markdown-formatted), then `typesetMath()` typesets each *finished* message (streamed
  replies on done, restored history on load — not per-token). Display equations are kept compact
  in the bubble: `mdLite` strips the blank lines the model puts around `$$…$$` (which
  `white-space:pre-wrap` would otherwise render as a tall gap) and the chat CSS trims
  MathJax's default `1em` display margin to `.35em`; wide equations scroll
  (`overflow-x:auto`) instead of overflowing.

## Roadmap (not yet built)

Polish: a thread-switcher that's nicer than the list overlay, delete-thread,
multiple highlights per passage, and an optional "apply this rewrite to the post"
action. See `ROADMAP.md`.
