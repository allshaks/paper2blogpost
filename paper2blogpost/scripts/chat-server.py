#!/usr/bin/env python3
"""
chat-server.py — ONE local companion server for ALL your paper2blogpost posts.
You set it up once; afterwards every post just works. It does two jobs:

  1. Serves a folder of posts (so there's no file:// / CORS friction). The landing
     page at / lists every post; each is served at /<post-name>/.
  2. Bridges each post's in-page chat to your local `claude` CLI (your Claude Code
     login — no API key). A chat thread maps to a `claude` session id (resumable),
     and threads + grounding live in that post's own <post>/chat/ folder.

Per-post state is created lazily: the first time a post is chatted with, the server
writes <post>/chat/CLAUDE.md from <post>/chat/paper.md (the grounding) and reads/
writes <post>/chat/threads.json. `claude` runs from that folder so it loads the
CLAUDE.md context automatically (cached, so it's cheap after the first turn).
Setting all this up costs NO model tokens — only actually chatting does.

Binds 127.0.0.1 only — it is NOT meant to be exposed to a network.

Run it (one of):
  python chat-server.py --install [--dir ~/.paper2blogpost/posts] [--port 8877]
      → installs a macOS LaunchAgent so it auto-starts at login (recommended).
  python chat-server.py [--dir <folder-of-posts | single-post>] [--port 8877]
      → run in the foreground. --dir may be a folder of posts OR one post folder.
      Default --dir is ~/.paper2blogpost/posts, the central store the skill builds into.
Then open http://127.0.0.1:<port>/ and pick a post.

Each post's front-end pings <post>/__chat/ping (a RELATIVE URL, so it works wherever
the post is mounted); if this server answers, the chat UI appears, otherwise the post
stays a plain static read.
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

# The one central store every post lives in. The skill builds each post here (and drops
# a convenience symlink back in your working dir), and this server serves the whole
# folder — so a post is "born" where the server already looks; nothing to copy.
POSTS_ROOT = Path.home() / ".paper2blogpost" / "posts"

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


INDEX_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your paper blog-posts</title>
<style>
  :root{{
    --bg:#faf8f4; --surface:#fffdf9; --ink:#23201b; --ink-soft:#5c5548; --ink-faint:#8f887b;
    --accent:#b8552f; --accent-soft:#f4e5da; --rule:#e9e3d8;
    --shadow:0 8px 30px rgba(40,30,20,.07), 0 2px 8px rgba(40,30,20,.05);
    color-scheme:light dark;
  }}
  @media (prefers-color-scheme:dark){{:root{{
    --bg:#15140f; --surface:#1f1d16; --ink:#ece7dc; --ink-soft:#c3bcac; --ink-faint:#8a8378;
    --accent:#dd8a60; --accent-soft:#2c2318; --rule:#332f26;
    --shadow:0 10px 34px rgba(0,0,0,.4);
  }}}}
  *{{box-sizing:border-box}}
  body{{margin:0; background:var(--bg); color:var(--ink); -webkit-font-smoothing:antialiased;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif; line-height:1.6}}
  .wrap{{max-width:760px; margin:0 auto; padding:13vh 24px 12vh}}
  .eyebrow{{font-size:12.5px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
    color:var(--accent); margin-bottom:14px}}
  h1{{font-family:'Iowan Old Style','Palatino Linotype',Charter,Georgia,serif;
    font-size:44px; line-height:1.08; letter-spacing:-.015em; margin:0 0 14px; font-weight:600}}
  .sub{{color:var(--ink-soft); font-size:18px; margin:0 0 42px; max-width:36em}}
  .grid{{display:flex; flex-direction:column; gap:12px}}
  a.post{{display:flex; align-items:center; gap:18px; text-decoration:none; color:inherit;
    background:var(--surface); border:1px solid var(--rule); border-radius:16px;
    padding:20px 22px; box-shadow:var(--shadow); transition:transform .16s ease, border-color .16s ease}}
  a.post:hover{{transform:translateY(-2px); border-color:var(--accent)}}
  a.post .body{{flex:1; min-width:0}}
  a.post .t{{font-family:'Iowan Old Style','Palatino Linotype',Charter,Georgia,serif;
    font-size:20px; font-weight:600; line-height:1.25; color:var(--ink)}}
  a.post .dek{{font-size:14.5px; color:var(--ink-soft); margin-top:4px;
    display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden}}
  a.post .badge{{display:inline-block; margin-left:9px; padding:1px 8px; border-radius:20px; vertical-align:middle;
    background:var(--accent); color:#fff; font-size:10px; font-weight:700; letter-spacing:.07em; text-transform:uppercase}}
  a.post .go{{flex:none; color:var(--ink-faint); font-size:22px; transition:transform .16s ease, color .16s ease}}
  a.post:hover .go{{color:var(--accent); transform:translateX(4px)}}
  .empty{{color:var(--ink-faint); background:var(--surface); border:1px dashed var(--rule);
    border-radius:16px; padding:30px 22px; text-align:center}}
  footer{{margin-top:40px; color:var(--ink-faint); font-size:12.5px}}
  footer code{{background:var(--accent-soft); color:var(--ink-soft); padding:1px 6px; border-radius:5px}}
</style></head><body>
<div class="wrap">
  <div class="eyebrow">Your library</div>
  <h1>Paper blog-posts</h1>
  <p class="sub">Friendly, readable versions of the papers you've converted — each one can chat about its own
  paper, grounded in the full text. Pick one to dive in.</p>
  <div class="grid">{rows}</div>
  <footer>{count} · served locally from <code>{root}</code> · built with the <b>paper2blogpost</b> skill</footer>
</div>
</body></html>"""


class Ctx:
    """State for ONE post: its paths, thread store, and the claude bridge. Grounds on
    the post's own `chat/paper.md`. Created lazily (per post) by `get_ctx`."""

    def __init__(self, post_dir: Path, model: str = None):
        self.root = post_dir.resolve()
        self.model = model
        self.chatdir = self.root / "chat"
        self.chatdir.mkdir(parents=True, exist_ok=True)
        paper_file = self.chatdir / "paper.md"
        paper_text = paper_file.read_text(errors="ignore") if paper_file.exists() else ""
        self.grounded = bool(paper_text)
        # CLAUDE.md is a DERIVED cache — rebuilt here on every start from paper.md + GUIDE
        # (paper.md is the source of truth; this file is how a tool-less `claude -p` gets
        # grounded, since it auto-loads CLAUDE.md but can't open paper.md itself).
        banner = ("<!-- AUTO-GENERATED — do not edit. Rebuilt on every server start from "
                  "this folder's paper.md + the server's GUIDE. Edits here are overwritten; "
                  "to change the grounding text, edit paper.md instead. -->\n\n")
        (self.chatdir / "CLAUDE.md").write_text(
            banner + GUIDE.format(paper=paper_text or "(no paper text was provided)"))
        self.threads_path = self.chatdir / "threads.json"
        self.defs_path = self.chatdir / "definitions.json"
        self.lock = threading.Lock()
        self.threads = self._load(self.threads_path)
        self.definitions = self._load(self.defs_path)   # id -> {anchor, term, definition, source, …}

    @staticmethod
    def _load(path):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return {}
        return {}

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

    def summarize_thread(self, tid):
        """A cached one/two-line summary of a thread (for the highlight hover popup).
        Regenerated only when the message count changes; Haiku, no paper needed here."""
        with self.lock:
            th = self.threads.get(tid)
            if not th:
                return {}
            msgs = list(th.get("messages", []))
            if th.get("summary") is not None and th.get("summaryTurns") == len(msgs):
                return {"summary": th.get("summary", ""), "conclusion": th.get("conclusion", "")}
        if not msgs:
            return {"summary": "", "conclusion": ""}
        transcript = "\n\n".join(
            f"{'Reader' if m['role'] == 'user' else 'Assistant'}: {m['text']}" for m in msgs)[:6000]
        full = []
        for ev in self.run_claude(SUMMARY_PROMPT + "\n\nCHAT:\n" + transcript, None,
                                  model="claude-haiku-4-5", effort=None, internet=False):
            if ev.get("type") == "stream_event":
                e = ev.get("event", {})
                if e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    full.append(e["delta"]["text"])
            elif ev.get("type") == "result" and not full and ev.get("result"):
                full.append(ev["result"])
        summary, conclusion = _parse_summary("".join(full))
        with self.lock:
            th = self.threads.get(tid)
            if th:
                th["summary"], th["conclusion"], th["summaryTurns"] = summary, conclusion, len(msgs)
                self._persist()
        return {"summary": summary, "conclusion": conclusion}

    # ---- definitions (select-text → Define) ----
    def define_list(self):
        with self.lock:
            return list(self.definitions.values())

    def save_definition(self, did, anchor, data):
        with self.lock:
            rec = {"id": did, "anchor": anchor, "created": time.time(), **data}
            self.definitions[did] = rec
            self.defs_path.write_text(json.dumps(self.definitions, indent=2))
            return rec

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


# One persistent server can serve MANY posts. Each post folder gets its own Ctx
# (its own chat/paper.md grounding + chat/threads.json), created lazily and cached.
SERVER = {"root": None, "model": None}     # filled in by main()
CTX_BY_POST = {}
_ctx_lock = threading.Lock()


def get_ctx(post_dir: Path) -> Ctx:
    key = str(post_dir.resolve())
    with _ctx_lock:
        ctx = CTX_BY_POST.get(key)
        if ctx is None:
            ctx = Ctx(post_dir, model=SERVER["model"])
            CTX_BY_POST[key] = ctx
        return ctx

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


# ---- Define (select-text → Define): a 3-tier lookup returning a small JSON object ----
DEFINE_MODEL = "claude-sonnet-5"
DEFINE_EFFORT = "medium"

DEFINE_PROMPT = """The reader selected the term "{term}" in this paper and wants it defined. \
Follow this strategy STRICTLY, in order, and stop at the first tier that works:

1. PAPER FIRST. Search THIS paper (your CLAUDE.md context) from the top for where "{term}" \
is defined or first introduced. If the paper defines or clearly explains it, use that. \
Set "source":"paper" and set "paper_quote" to a short VERBATIM excerpt (<=160 chars) copied \
exactly from the paper at the point of definition, so it can be located on the page.

2. ELSE FOLLOW A REFERENCE. If the paper does not define it, find where "{term}" appears and \
look for a citation near that appearance. If there is one, look that reference up on the web \
(use your web search / fetch tools) and define the term from that source. Set "source":"reference" \
and fill "reference" with {{"num": <the [N] citation number if identifiable, else null>, \
"title": "<work title>", "url": "<best URL to the source>"}}.

3. ELSE FROM MEMORY. If the paper neither defines it nor cites a relevant reference for it, \
define it from your own knowledge. Set "source":"memory".

Keep "definition" to 1-3 clear, colloquial sentences — as readable as a good blog post, \
explaining any jargon in passing. Do not hedge about which tier you used; just fill the fields. \
Write any formulas or symbols in the definition as LaTeX — inline math in single dollar signs \
($...$) and any displayed formula in double dollar signs ($$...$$), using real commands \
(\\mathbf, \\sum, _, ^, \\alpha, …); the popup renders them. Keep the JSON valid: escape each \
LaTeX backslash as \\\\ inside the string.

The reader's immediate context (the paragraph around their selection):
"{context}"

Respond with ONLY a single JSON object and nothing else:
{{"term": "{term}", "definition": "...", "source": "paper|reference|memory", \
"paper_quote": "... (only when source=paper)", \
"reference": {{"num": N_or_null, "title": "...", "url": "..."}} (only when source=reference)}}"""


def _parse_define(text, term):
    """Pull the JSON object out of the model's reply, defensively. LaTeX in the
    definition often reaches us with unescaped backslashes (invalid JSON), so if the
    raw parse fails, retry with lone backslashes doubled."""
    s = (text or "").strip()
    i, j = s.find("{"), s.rfind("}")
    if i >= 0 and j > i:
        blob = s[i:j + 1]
        # a backslash NOT starting a valid JSON escape (\" \\ \/ \b \f \n \r \t \u) → double it
        repaired = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', blob)
        for candidate in (blob, repaired):
            try:
                obj = json.loads(candidate)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("definition"):
                obj.setdefault("term", term)
                if obj.get("source") not in ("paper", "reference", "memory"):
                    obj["source"] = "memory"
                return obj
    # couldn't parse structured output — fall back to treating the reply as a plain definition
    return {"term": term, "definition": s or "(no definition returned)", "source": "memory"}


def _norm_term(t):
    """Fold a term for dedup: lowercase, drop surrounding punctuation, and squeeze out
    every space / newline / hyphen / underscore so "Cosine-Similarity", "cosine
    similarity", and "cosine\\nsimilarity" all collapse to the same key."""
    t = (t or "").lower().strip()
    t = re.sub(r"^[^\w]+|[^\w]+$", "", t)     # strip leading/trailing punctuation
    return re.sub(r"[\s\-_]+", "", t)


# One-line hover summary of a chat thread (generated by Haiku, cached per thread).
SUMMARY_PROMPT = (
    "Below is a short chat between a reader and an assistant about a passage in a paper. "
    "Summarize it in ONE very short, informal sentence — what the reader was after, or what it "
    "was about. If the chat reached a clear answer or conclusion, add a SECOND short sentence "
    "with it, prefixed exactly 'Conclusion: '. If there's no real conclusion yet, give only the "
    "first sentence. No preamble, no markdown — just the 1-2 sentences.")


def _parse_summary(text):
    # collapse to one line, then split on the LAST "Conclusion:" marker wherever it sits
    # (the model often writes it inline, not on its own line)
    text = re.sub(r"\s+", " ", (text or "").strip())
    marks = list(re.finditer(r"(?i)\bconclusion\s*:\s*", text))
    if marks:
        m = marks[-1]
        return text[:m.start()].strip(), text[m.end():].strip()
    return text, ""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(SERVER["root"]), **k)

    def log_message(self, *a):
        pass  # quiet

    # ---- which post does a /__chat/ request belong to? ----
    def _chat_route(self):
        """For a `…/__chat/<endpoint>` path, return (post_dir | None, endpoint). The post
        is the path prefix before `/__chat/` (empty prefix = the root is itself a post).
        Returns (None, None) when the path isn't a chat path."""
        path = urlsplit(self.path).path
        marker = "/__chat/"
        i = path.find(marker)
        if i < 0:
            return None, None
        endpoint = path[i + len(marker):]
        sub = unquote(path[:i]).strip("/")
        root = SERVER["root"]
        post_dir = (root / sub) if sub else root
        try:
            post_dir = post_dir.resolve()
            post_dir.relative_to(root.resolve())     # guard against path traversal
        except Exception:
            return None, endpoint
        return (post_dir if post_dir.is_dir() else None), endpoint

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
        post_dir, endpoint = self._chat_route()
        if endpoint is not None:
            if endpoint == "ping":
                return self._json({"ok": True})            # server is up (post-agnostic)
            if post_dir is None:
                return self._json({"error": "unknown post"}, 404)
            ctx = get_ctx(post_dir)
            if endpoint == "threads":
                return self._json(ctx.thread_list())
            if endpoint.startswith("thread/"):
                return self._json(ctx.get_thread(endpoint.split("/", 1)[1]) or {})
            if endpoint == "definitions":
                return self._json(ctx.define_list())
            if endpoint.startswith("summary/"):
                return self._json(ctx.summarize_thread(endpoint.split("/", 1)[1]))
            return self._json({"error": "not found"}, 404)
        # static files; a bare "/" with no index.html at the root → the post listing
        p = urlsplit(self.path).path
        if p in ("/", "") and not (SERVER["root"] / "index.html").exists():
            return self._serve_index()
        return super().do_GET()

    def do_POST(self):
        post_dir, endpoint = self._chat_route()
        if endpoint in ("send", "define"):
            if post_dir is None:
                return self._json({"error": "unknown post"}, 404)
            ctx = get_ctx(post_dir)
            return self._chat(ctx) if endpoint == "send" else self._define(ctx)
        self.send_error(404)

    # ---- landing page: list every post under the root ----
    def _serve_index(self):
        root = SERVER["root"]
        posts = []
        for child in sorted(root.iterdir(), key=lambda c: c.name.lower()):
            idx = child / "index.html"
            if child.is_dir() and idx.exists():
                title, dek, concise = self._meta_of(idx)
                posts.append((child.name, title or child.name, dek, concise))
        cards = []
        for name, title, dek, concise in posts:
            badge = '<span class="badge">Summary</span>' if concise else ''
            dek_html = f'<div class="dek">{html.escape(dek)}</div>' if dek else ''
            cards.append(
                f'<a class="post" href="/{html.escape(name)}/">'
                f'<div class="body"><div class="t">{html.escape(title)}{badge}</div>{dek_html}</div>'
                f'<span class="go">&rarr;</span></a>'
            )
        rows = "\n".join(cards) or ('<div class="empty">No posts here yet — build one with the '
                                    'paper2blogpost skill; it lands in this folder automatically.</div>')
        count = f"{len(posts)} post" + ("" if len(posts) == 1 else "s")
        body = INDEX_HTML.format(rows=rows, root=html.escape(str(root)), count=count).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _meta_of(index_path):
        """(title, dek, is_concise) for a post's index.html — for the landing-page cards.
        Reads a bounded prefix: the <title> is near the top and the hero (.dek) sits just
        after the inlined CSS, so ~60 KB comfortably covers both even for a big post."""
        try:
            txt = index_path.read_text(errors="ignore")[:60000]
        except Exception:
            return (None, None, False)
        def clean(m):
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None
        title = clean(re.search(r"<title>(.*?)</title>", txt, re.I | re.S))
        dek = clean(re.search(r'<p[^>]*class="dek"[^>]*>(.*?)</p>', txt, re.I | re.S))
        concise = bool(re.search(r'<body[^>]*\bclass="[^"]*\bconcise\b', txt, re.I))
        return (title, dek, concise)

    def _chat(self, ctx):
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

        th = ctx.get_thread(tid)
        session_id = th.get("sessionId") if th else None

        self._sse_open()
        text, new_sid = self._run(ctx, msg, session_id, model, effort, internet, stream_text=True)
        text = text.strip()
        # store the reader's raw message (or a label for actions with no typed text)
        display = raw or ("Rewrite this for clarity" if kind == "rewrite" else
                          ("(about the highlighted passage)" if quote else msg))
        ctx.save_turn(tid, new_sid, anchor, kind, display, text,
                      settings={"model": model, "effort": effort, "internet": internet})
        self._sse({"done": True, "threadId": tid, "sessionId": new_sid})

    def _run(self, ctx, message, session_id, model, effort, internet, stream_text=True):
        """Stream one claude turn: always emit phase pills; emit text deltas only when
        stream_text. Returns (full_text, new_session_id). Caller must _sse_open() first."""
        full, new_sid = [], session_id
        for ev in ctx.run_claude(message, session_id, model=model, effort=effort, internet=internet):
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
                    if stream_text:
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
                    if stream_text:
                        self._sse({"delta": ev["result"]})
            elif t == "_error":
                self._sse({"phase": None})
                self._sse({"error": ev.get("message", "claude error")})
        return "".join(full), new_sid

    def _define(self, ctx):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad request"}, 400)
        anchor = data.get("anchor") or {}
        term = (data.get("term") or anchor.get("quote") or "").strip()
        context = (data.get("context") or "").strip()[:1500]
        if not term:
            return self._json({"error": "no term"}, 400)

        # Dedup: if this term (modulo case / space / newline / hyphen) was already defined,
        # reuse that definition for the new selection — no LLM call.
        norm = _norm_term(term)
        prior = next((r for r in ctx.definitions.values() if _norm_term(r.get("term", "")) == norm), None)
        self._sse_open()
        if prior:
            obj = {k: prior[k] for k in ("term", "definition", "source", "paper_quote", "reference")
                   if prior.get(k) is not None}
            obj["reused"] = True
            did = uuid.uuid4().hex
            ctx.save_definition(did, anchor, obj)
            return self._sse({"define": {"id": did, **obj}, "done": True})

        msg = DEFINE_PROMPT.format(term=term, context=context or "(none provided)")
        # Sonnet 5 / medium, internet ON — tier 2 may need to follow a reference on the web.
        text, _ = self._run(ctx, msg, None, DEFINE_MODEL, DEFINE_EFFORT, True, stream_text=False)
        obj = _parse_define(text, term)
        did = uuid.uuid4().hex
        ctx.save_definition(did, anchor, obj)
        self._sse({"define": {"id": did, **obj}, "done": True})


# ---------------------------------------------------------------------------
# Auto-start at login (macOS launchd). `--install` writes a LaunchAgent so the
# server is always running — open any post and chat just works, no manual launch.
# ---------------------------------------------------------------------------
LAUNCHD_LABEL = "com.paper2blogpost.chat"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def _support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "paper2blogpost"


def install_launchd(root: Path, port: int, model: str):
    import plistlib
    import shutil
    if sys.platform != "darwin":
        raise SystemExit("--install sets up a macOS LaunchAgent; on Linux use systemd --user "
                         "or just run the server in the background. See references/chat-mode.md.")
    # A LaunchAgent runs detached from any Terminal — it does NOT inherit the shell's file
    # permissions. If this script lives under a TCC-protected folder (Desktop/Documents/
    # Downloads/iCloud Drive/…), which it commonly does if the skill sits in a project repo,
    # the launchd process gets "Operation not permitted" trying to even read the file, and
    # macOS's Full Disk Access picker won't let you grant access to a symlink (which python3
    # binaries under Xcode's Command Line Tools usually are) — a dead end either way.
    # Fix: copy the script to Application Support, which macOS does NOT protect (it's the
    # standard place for a background helper's own files), and launch from there instead.
    # Re-run --install whenever the skill's chat-server.py is updated to refresh this copy.
    support_dir = _support_dir()
    support_dir.mkdir(parents=True, exist_ok=True)
    installed_script = support_dir / "chat-server.py"
    shutil.copy2(Path(__file__).resolve(), installed_script)

    prog = [sys.executable, str(installed_script), "--dir", str(root), "--port", str(port)]
    if model:
        prog += ["--model", model]
    logdir = Path.home() / "Library" / "Logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log = str(logdir / "paper2blogpost-chat.log")
    plist = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": prog,
        "RunAtLoad": True,
        "KeepAlive": True,                 # restart if it ever dies
        "WorkingDirectory": str(root),
        "StandardOutPath": log,
        "StandardErrorPath": log,
        # launchd jobs get a bare PATH; carry the current one so `claude` is found.
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin")},
    }
    p = _plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
    r = subprocess.run(["launchctl", "load", "-w", str(p)], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"launchctl load failed: {r.stderr.strip() or r.stdout.strip()}")
    print(f"✓ Installed — the chat server now auto-starts at login and is running now.")
    print(f"  serving:  {root}  →  http://127.0.0.1:{port}/")
    print(f"  running:  {installed_script}  (a copy — re-run --install after script updates)")
    print(f"  logs:     {log}")
    print(f"  uninstall: python {Path(__file__).name} --uninstall")


def uninstall_launchd():
    p = _plist_path()
    found = p.exists()
    if found:
        subprocess.run(["launchctl", "unload", "-w", str(p)], capture_output=True)
        p.unlink()
    support = _support_dir()
    if support.exists():
        import shutil
        shutil.rmtree(support, ignore_errors=True)
        found = True
    print("✓ Uninstalled — auto-start removed and the server stopped." if found
          else "Nothing to uninstall (no LaunchAgent found).")


def main():
    ap = argparse.ArgumentParser(
        description="Local companion server for paper2blogpost. Serves one post OR a whole "
                    "folder of posts, and bridges each post's in-page chat to your `claude` CLI.")
    ap.add_argument("--dir", default=str(POSTS_ROOT),
                    help="a single post folder, OR a folder containing many post folders "
                         "(default: ~/.paper2blogpost/posts, the central store the skill builds into)")
    ap.add_argument("--port", type=int, default=8877)
    ap.add_argument("--model", help="claude model for the chat (default: your CLI default; "
                                     "e.g. claude-haiku-4-5 / claude-sonnet-4-6 for snappier replies)")
    ap.add_argument("--install", action="store_true",
                    help="install a macOS LaunchAgent so the server auto-starts at login, then exit")
    ap.add_argument("--uninstall", action="store_true", help="remove the LaunchAgent, then exit")
    args = ap.parse_args()

    root = Path(args.dir).expanduser().resolve()

    if args.uninstall:
        return uninstall_launchd()
    if args.install:
        root.mkdir(parents=True, exist_ok=True)
        return install_launchd(root, args.port, args.model)

    root.mkdir(parents=True, exist_ok=True)
    SERVER["root"] = root
    SERVER["model"] = args.model

    single = (root / "index.html").exists()
    posts = [] if single else [c.name for c in sorted(root.iterdir())
                               if c.is_dir() and (c / "index.html").exists()]

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"paper2blogpost chat server → {url}")
    if single:
        print(f"  serving:  {root}  (single post)")
    else:
        print(f"  serving:  {root}  ({len(posts)} post{'' if len(posts)==1 else 's'})")
        for name in posts[:12]:
            print(f"     • {url}{name}/")
    print("  Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")


if __name__ == "__main__":
    main()
