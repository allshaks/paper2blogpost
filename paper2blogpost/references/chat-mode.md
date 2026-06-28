# Chat mode (local companion server)

The post can become something you *think with*: a collapsible sidebar chat that
answers questions about the paper, grounded in its full text. This is a **local
powered mode** — it lights up only when a small companion server is running next
to the post; a plain or shared copy stays a clean static read.

## How it fits together

- **`scripts/chat-server.py`** — a local server (binds `127.0.0.1` only) that:
  1. serves the post folder (no `file://` / CORS issues), and
  2. bridges the in-page chat to the user's **`claude` CLI** (their Claude Code
     login — no API key). Each chat thread maps to a `claude` session id, so a
     thread is resumable; threads persist to `<post>/chat/threads.json`.
- **Grounding**: at startup the server writes `<post>/chat/CLAUDE.md` = a guide +
  the paper's full text, and runs `claude` from `<post>/chat/`, so every turn is
  grounded in the paper (cached after the first call, so it's cheap).
- **Front-end**: the template's `#chat` sidebar pings `/__chat/ping`; if the
  server answers, the "💬 Ask Claude" launcher appears. Messages stream back token
  by token over SSE.

The server quiets the user's global Claude Code environment selectively — it loads
**no MCP servers** (`--strict-mcp-config --mcp-config '{"mcpServers":{}}'`) and
appends a persona system prompt that overrides any injected output style (so you
don't get "★ Insight" blocks in a reader chat). It deliberately does **not** use
`--bare`, because that would force an API key and drop the CLAUDE.md grounding.

## What the skill must do at build time

For chat mode to ground itself, drop the paper's plain text into the post:

```
<post>/chat/paper.md      ← the extracted paper text (build/text/full.txt)
```

The server reads that by default (or take `--paper <file>`). Everything else
(`CLAUDE.md`, `threads.json`) the server creates itself. If `paper.md` is absent
the chat still works but won't be grounded in the paper.

## Launching it (tell the user)

```bash
python scripts/chat-server.py --dir <post-folder> [--model claude-haiku-4-5]
# then open the printed http://127.0.0.1:8765/ URL
```

`--model` is the *default*; the reader can also pick the model and effort live in
the chat header (see below), which overrides it per message.

## In the chat UI

- **Model + effort pickers** in the header (Haiku / Sonnet / Opus; low…max). Sent
  per message; effort is dropped automatically for Haiku (which rejects it).
- **🌐 Web toggle** — off runs a pure grounded chat (`--tools ""`, fast); on gives
  Claude `WebSearch`/`WebFetch` so it can look things up. Remembered in localStorage.
- **Multiple chats** — `＋` starts a new thread; `☰` lists every chat opened in this
  paper (with a `passage`/`rewrite` badge) to switch between them. Threads live in
  `chat/threads.json`, each mapped to a resumable `claude` session.
- **Select any passage** → a small bubble offers **Ask** (opens a thread seeded with
  that passage so your question has context) or **Rewrite for clarity** (Claude
  returns a clearer version of the passage). Either wraps the selection in a
  `<mark class="q-highlight" data-thread="…">` that *stays* as a visible trace;
  clicking it reopens that exact thread. Highlights persist via a text-offset
  `anchor` ({quote, sectionId, start, length}) stored on the thread and re-applied
  on load.
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

## Roadmap (not yet built)

Polish: a thread-switcher that's nicer than the list overlay, delete-thread,
multiple highlights per passage, and an optional "apply this rewrite to the post"
action. See `ROADMAP.md`.
