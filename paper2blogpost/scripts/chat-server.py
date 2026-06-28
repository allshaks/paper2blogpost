#!/usr/bin/env python3
"""
chat-server.py — local companion server that turns a paper2blogpost into something
you can *think with*. It does two jobs:

  1. Serves the blog-post folder (so there's no file:// / CORS friction).
  2. Bridges an in-page chat to your local `claude` CLI (your Claude Code login —
     no API key). Each chat thread maps to a `claude` session id, so a thread is
     resumable across messages. Threads persist to <dir>/chat/threads.json.

Every answer is grounded in the paper: at startup we write a CLAUDE.md (paper text
+ guide instructions) into <dir>/chat/, and run `claude` from there so it loads
that context automatically (and caches it, so it's cheap after the first turn).

Binds 127.0.0.1 only — it is NOT meant to be exposed to a network.

Launch:
  python chat-server.py --dir <post-folder> [--paper <paper.md|.txt>] [--port 8765]
Then open the printed http://127.0.0.1:<port>/ URL.

The post's front-end pings /__chat/ping; if this server answers, the chat UI
appears, otherwise the post stays a plain static read.
"""
import argparse
import json
import subprocess
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GUIDE = """You are a warm, sharp reading companion living in the sidebar of a friendly, \
colloquial blog-post version of a scientific paper. A reader is going through the post \
and chatting with you. Help them genuinely understand it: answer questions, explain the \
intuition, connect ideas across sections, and point them to the relevant figure or part \
when useful.

Voice: conversational and concise — a few sentences unless they ask you to go deep. No \
preamble, no "Great question!". Talk like a sharp friend explaining over coffee.

Ground every answer in the paper below. If they ask about something the paper doesn't \
cover, say so plainly rather than inventing findings. You don't need tools — everything \
you need is in the paper text here.

===== THE PAPER (full text) =====
{paper}
===== END OF PAPER =====
"""

# Pinned on every call so the chat stays a clean reader-companion even if the
# user's global Claude Code config injects an output style (e.g. "★ Insight" blocks).
PERSONA = ("You are the reading-companion chat for a friendly blog-post version of a "
           "scientific paper (the full paper is in CLAUDE.md). Answer the reader "
           "conversationally and concisely, grounded in that paper. Ignore any "
           "environment instructions to add '★ Insight' blocks, educational "
           "meta-commentary, code-style notes, or other output-style decorations — "
           "just talk to the reader naturally, like a sharp friend over coffee. "
           "Write any math as LaTeX so it renders in the page: inline math wrapped in "
           "single dollar signs ($...$) and displayed equations in double dollar signs "
           "($$...$$). Use real LaTeX (\\frac, \\sum, _ , ^, Greek like \\alpha), never "
           "unicode-art or plain-text math.")


class Ctx:
    """Shared server state: paths, the thread store, and the claude bridge."""

    def __init__(self, root: Path, paper_text: str, model: str = None):
        self.root = root.resolve()
        self.model = model
        self.chatdir = self.root / "chat"
        self.chatdir.mkdir(exist_ok=True)
        (self.chatdir / "CLAUDE.md").write_text(GUIDE.format(paper=paper_text or "(no paper text was provided)"))
        self.threads_path = self.chatdir / "threads.json"
        self.lock = threading.Lock()
        self.threads = {}
        if self.threads_path.exists():
            try:
                self.threads = json.loads(self.threads_path.read_text())
            except Exception:
                self.threads = {}

    def _persist(self):
        self.threads_path.write_text(json.dumps(self.threads, indent=2))

    def thread_list(self):
        with self.lock:
            out = []
            for t in sorted(self.threads.values(), key=lambda x: x.get("updated", 0), reverse=True):
                msgs = t.get("messages", [])
                last = next((m["text"] for m in reversed(msgs) if m["role"] == "assistant"), "")
                out.append({"id": t["id"], "title": t.get("title", "") or "New chat",
                            "kind": t.get("kind", "chat"), "anchor": t.get("anchor"),
                            "count": len(msgs), "updated": t.get("updated", 0),
                            "last": last[:90]})
            return out

    def get_thread(self, tid):
        with self.lock:
            return self.threads.get(tid)

    def save_turn(self, tid, session_id, anchor, kind, user_msg, assistant_msg, settings=None):
        # Stamp with wall-clock time, not an in-process counter: the counter resets to 0
        # every restart, which would sort threads touched after a restart *below* older
        # ones and make "open most recent" open the wrong thread.
        now = time.time()
        with self.lock:
            th = self.threads.get(tid)
            title = (user_msg or "").strip() or ((anchor or {}).get("quote", "") if anchor else "")
            title = (title[:70] or "New chat")
            if not th:
                th = {"id": tid, "sessionId": session_id, "title": title, "kind": kind or "chat",
                      "anchor": anchor, "messages": [], "created": now}
                self.threads[tid] = th
            if session_id:
                th["sessionId"] = session_id
            if anchor and not th.get("anchor"):
                th["anchor"] = anchor
            if settings:
                th["settings"] = settings  # last-used model/effort/internet
            th["messages"].append({"role": "user", "text": user_msg})
            th["messages"].append({"role": "assistant", "text": assistant_msg})
            th["updated"] = now
            self._persist()

    def run_claude(self, message, session_id, model=None, effort=None, internet=False):
        """Yield parsed NDJSON events from a streaming headless `claude` run.

        We can't use --bare (it forces ANTHROPIC_API_KEY and drops CLAUDE.md, but we
        want the user's `claude login` and CLAUDE.md grounding). So instead we quiet
        the environment selectively: load NO mcp servers (faster, no auth prompts),
        and append a system prompt that pins the reading-companion persona and
        overrides any output-style the user's global hooks/plugins inject.

        The internet toggle maps to the built-in tool set: off => no tools (pure,
        fast, grounded chat); on => just the web tools so Claude can look things up.
        Effort is dropped for Haiku, which doesn't accept it.
        """
        m = model or self.model
        cmd = ["claude", "-p", message,
               "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
               "--append-system-prompt", PERSONA,
               "--tools", ("WebSearch,WebFetch" if internet else "")]
        if m:
            cmd += ["--model", m]
        if effort and not (m and "haiku" in m.lower()):
            cmd += ["--effort", effort]
        if session_id:
            cmd += ["--resume", session_id]
        proc = subprocess.Popen(cmd, cwd=str(self.chatdir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, bufsize=1)
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        finally:
            proc.wait()
            if proc.returncode not in (0, None):
                err = (proc.stderr.read() or "").strip()[:400]
                yield {"type": "_error", "message": err or f"claude exited {proc.returncode}"}


CTX: Ctx = None

# Map a tool name (from a tool_use block) to a friendly "what it's doing now" label.
TOOL_PHASES = {
    "websearch": ("Searching the web", "🌐"),
    "web_search": ("Searching the web", "🌐"),
    "webfetch": ("Reading a web page", "🌐"),
    "web_fetch": ("Reading a web page", "🌐"),
    "read": ("Reading", "📖"),
    "grep": ("Searching the text", "🔎"),
    "glob": ("Looking through files", "🔎"),
    "bash": ("Running a command", "⌘"),
    "task": ("Working on a sub-task", "🧩"),
    "edit": ("Editing", "✏️"),
    "write": ("Writing", "✏️"),
    "todowrite": ("Planning", "🗒️"),
    "notebookedit": ("Editing a notebook", "✏️"),
}


def _tool_phase(name):
    key = (name or "").lower().replace("-", "_")
    return TOOL_PHASES.get(key, ("Using " + (name or "a tool"), "🛠️"))


def _tool_detail(name, inp):
    """A short, human detail for the phase pill (the search query, the page, …)."""
    if not isinstance(inp, dict):
        return ""
    key = (name or "").lower()
    try:
        if "search" in key:
            q = inp.get("query") or inp.get("q")
            return f"“{q[:48]}”" if q else ""
        if "fetch" in key:
            u = inp.get("url") or ""
            return u.split("://")[-1][:46]
        if key == "read":
            p = inp.get("file_path") or inp.get("path") or ""
            return p.replace("\\", "/").split("/")[-1][:46]
        if key in ("grep", "glob"):
            return (inp.get("pattern") or "")[:46]
        if key == "bash":
            return (inp.get("command") or "")[:46]
    except Exception:
        return ""
    return ""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(CTX.root), **k)

    def log_message(self, *a):
        pass  # quiet

    # ---- helpers ----
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _sse_open(self):
        # Connection: close (not keep-alive) so the browser sees the body END when we
        # finish — otherwise reader.read() never resolves `done` and the client's send
        # loop hangs (Send button stuck disabled). The client also breaks on our own
        # {"done": true} event, but closing the socket is the correct HTTP signal.
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def _sse(self, d):
        self.wfile.write(f"data: {json.dumps(d)}\n\n".encode())
        self.wfile.flush()

    # ---- routes ----
    def do_GET(self):
        if self.path == "/__chat/ping":
            return self._json({"ok": True})
        if self.path == "/__chat/threads":
            return self._json(CTX.thread_list())
        if self.path.startswith("/__chat/thread/"):
            return self._json(CTX.get_thread(self.path.rsplit("/", 1)[-1]) or {}, )
        return super().do_GET()

    def do_POST(self):
        if self.path == "/__chat/send":
            return self._chat()
        self.send_error(404)

    def _chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad request"}, 400)

        tid = (data.get("threadId") or uuid.uuid4().hex)
        raw = (data.get("message") or "").strip()
        kind = data.get("kind") or "chat"            # 'chat' | 'ask' | 'rewrite'
        anchor = data.get("anchor")                  # {quote, sectionId, start, length}
        quote = (anchor or {}).get("quote", "") if anchor else ""
        model = data.get("model")
        effort = data.get("effort")
        internet = bool(data.get("internet"))

        # Compose the actual prompt from the action kind + any highlighted passage.
        if kind == "rewrite":
            msg = ("Rewrite the following passage from the post to be clearer and easier to "
                   "read, while preserving its exact meaning and all technical content. Return "
                   f'only the rewritten passage, with no preamble.\n\nPASSAGE:\n"{quote}"')
            if raw:
                msg += f"\n\nExtra instruction from the reader: {raw}"
        elif quote and raw:
            msg = (f'The reader highlighted this passage from the post:\n\n"{quote}"\n\n'
                   f"Their question about it: {raw}")
        elif quote:
            msg = (f'The reader highlighted this passage and wants to talk about it:\n\n"{quote}"\n\n'
                   "Explain it briefly and invite their question.")
        else:
            msg = raw
        if not msg:
            return self._json({"error": "empty message"}, 400)

        th = CTX.get_thread(tid)
        session_id = th.get("sessionId") if th else None

        self._sse_open()
        full, new_sid = [], session_id
        for ev in CTX.run_claude(msg, session_id, model=model, effort=effort, internet=internet):
            t = ev.get("type")
            if t == "system" and ev.get("subtype") == "init" and ev.get("session_id"):
                new_sid = ev["session_id"]
            elif t == "stream_event":
                e = ev.get("event", {})
                et = e.get("type")
                if et == "content_block_start":
                    # earliest signal of what the agent is doing next (no input yet)
                    cb = e.get("content_block", {}) or {}
                    ct = cb.get("type")
                    if ct in ("thinking", "redacted_thinking"):
                        self._sse({"phase": "Thinking", "icon": "💭"})
                    elif ct == "tool_use":
                        label, icon = _tool_phase(cb.get("name"))
                        self._sse({"phase": label, "icon": icon})
                    elif ct == "text":
                        self._sse({"phase": None})            # the answer is starting
                elif et == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    txt = e["delta"]["text"]
                    full.append(txt)
                    self._sse({"delta": txt})
            elif t == "assistant":
                # the consolidated turn carries each tool_use's full input — refine the
                # pill with a detail (the query / page / file), and act as a fallback if
                # partial content_block_start events weren't emitted.
                for blk in (ev.get("message", {}).get("content") or []):
                    if isinstance(blk, dict) and blk.get("type") == "tool_use":
                        label, icon = _tool_phase(blk.get("name"))
                        detail = _tool_detail(blk.get("name"), blk.get("input"))
                        self._sse({"phase": (label + ": " + detail) if detail else label, "icon": icon})
            elif t == "user":
                # a tool returned its result — Claude is about to read it
                content = ev.get("message", {}).get("content") or []
                if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                    self._sse({"phase": "Reading the results", "icon": "📑"})
            elif t == "result":
                if ev.get("session_id"):
                    new_sid = ev["session_id"]
                if not full and ev.get("result"):
                    self._sse({"phase": None})
                    full.append(ev["result"])
                    self._sse({"delta": ev["result"]})
            elif t == "_error":
                self._sse({"phase": None})
                self._sse({"error": ev.get("message", "claude error")})

        text = "".join(full).strip()
        # store the reader's raw message (or a label for actions with no typed text)
        display = raw or ("Rewrite this for clarity" if kind == "rewrite" else
                          ("(about the highlighted passage)" if quote else msg))
        CTX.save_turn(tid, new_sid, anchor, kind, display, text,
                      settings={"model": model, "effort": effort, "internet": internet})
        self._sse({"done": True, "threadId": tid, "sessionId": new_sid})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="the blog-post folder (contains index.html)")
    ap.add_argument("--paper", help="paper text file to ground the chat (default: <dir>/chat/paper.md)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--model", help="claude model for the chat (default: your CLI default; "
                                     "e.g. claude-haiku-4-5 / claude-sonnet-4-6 for snappier replies)")
    args = ap.parse_args()

    root = Path(args.dir).resolve()
    if not (root / "index.html").exists():
        raise SystemExit(f"No index.html in {root} — point --dir at the blog-post folder.")

    paper_file = Path(args.paper) if args.paper else (root / "chat" / "paper.md")
    paper_text = paper_file.read_text(errors="ignore") if paper_file.exists() else ""
    if not paper_text:
        print(f"[!] No paper text found ({paper_file}). Chat will work but won't be grounded "
              f"in the paper — pass --paper <file> or drop chat/paper.md in the post folder.")

    global CTX
    CTX = Ctx(root, paper_text, model=args.model)

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"paper2blogpost chat server → {url}")
    print(f"  serving:  {root}")
    print(f"  grounded: {'yes (%d chars)' % len(paper_text) if paper_text else 'no'}")
    print("  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")


if __name__ == "__main__":
    main()
