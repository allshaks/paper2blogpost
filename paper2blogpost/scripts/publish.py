#!/usr/bin/env python3
"""
publish.py — drop a convenience pointer to a post in your working directory.

Every post is built into the central store (~/.paper2blogpost/posts/<slug>/) so the
one chat server always finds it. That's the source of truth. This script just leaves a
shortcut where you were working so you can open the post from there:

  python publish.py ~/.paper2blogpost/posts/<slug>-blogpost
      → creates ./<slug>-blogpost  ⇒  ~/.paper2blogpost/posts/<slug>-blogpost  (symlink)

The symlink is BEST-EFFORT and never load-bearing — figures, chat, assembly, and
--upgrade all run off the real central path. If a symlink can't be made (e.g. Windows
without Developer Mode / admin), we fall back to a tiny `<name>.html` redirect and
always print the real path, so nothing is lost but the convenience.

If the working dir is inside a git repo, the pointer's name is added to a local
`.gitignore` — it points at an absolute path under your home dir, so it shouldn't be
committed.
"""
import argparse
import os
import sys
from pathlib import Path


def in_git_repo(path: Path) -> bool:
    """True if `path` sits inside a git work tree (a `.git` dir OR file — worktrees/
    submodules use a file). Cheap upward walk, no subprocess."""
    for p in [path, *path.parents]:
        if (p / ".git").exists():
            return True
    return False


def ensure_gitignored(dir_: Path, names) -> None:
    """Append each name to dir_/.gitignore if not already listed (idempotent)."""
    gi = dir_ / ".gitignore"
    existing = set()
    if gi.exists():
        existing = {ln.strip() for ln in gi.read_text().splitlines()}
    missing = [n for n in names if n not in existing]
    if not missing:
        return
    prefix = "" if (not gi.exists() or gi.read_text().endswith("\n")) else "\n"
    with gi.open("a") as f:
        f.write(prefix + "\n".join(missing) + "\n")


def write_pointer(pointer: Path, post_dir: Path) -> None:
    """A one-click fallback when we can't symlink: an HTML file that redirects to the
    post's index.html by absolute file:// URL."""
    target = (post_dir / "index.html").resolve().as_uri()
    pointer.write_text(
        f'<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        f'<title>Open this post</title>'
        f'<p>Your post lives at <a href="{target}">{target}</a>.</p>\n'
    )


def publish(post_dir: Path, at=None) -> int:
    post_dir = post_dir.expanduser().resolve()
    if not (post_dir / "index.html").exists():
        print(f"error: {post_dir} has no index.html — is it a finished post?", file=sys.stderr)
        return 2

    link = (at.expanduser() if at else Path.cwd() / post_dir.name)
    link_abs = link.absolute()

    # Pointer path IS the post itself (e.g. the skill was run inside the central store) —
    # nothing to do.
    if link_abs == post_dir:
        print(f"✓ Post is already at {post_dir} (no separate pointer needed).")
        return 0

    made = None  # "symlink" | "pointer"
    # A stale symlink from a previous run is safe to refresh; a real file/dir is not —
    # never clobber the user's own data.
    if link_abs.is_symlink():
        try:
            if link_abs.resolve() == post_dir:
                made = "symlink"  # already correct
            else:
                link_abs.unlink()
        except OSError:
            pass
    elif link_abs.exists():
        print(f"⚠ {link_abs} already exists and isn't a symlink — leaving it untouched.")
        pointer = link_abs.with_name(link_abs.name + ".html")
        write_pointer(pointer, post_dir)
        made = "pointer"
        _report(post_dir, made, pointer)
        _maybe_ignore(link_abs, made)
        return 0

    if made != "symlink":
        try:
            os.symlink(post_dir, link_abs, target_is_directory=True)
            made = "symlink"
        except OSError as e:
            # Windows without privilege lands here; degrade to a printed path + pointer.
            print(f"(couldn't create a symlink: {e.__class__.__name__} — leaving a redirect instead)")
            pointer = link_abs.with_name(link_abs.name + ".html")
            write_pointer(pointer, post_dir)
            made = "pointer"
            _report(post_dir, made, pointer)
            _maybe_ignore(link_abs, made)
            return 0

    _report(post_dir, made, link_abs)
    _maybe_ignore(link_abs, made)
    return 0


def _report(post_dir: Path, made: str, at: Path) -> None:
    if made == "symlink":
        print(f"✓ Linked  {at}  →  {post_dir}")
    else:
        print(f"✓ Wrote pointer  {at}")
    print(f"  the post lives at: {post_dir}")


def _maybe_ignore(link_abs: Path, made: str) -> None:
    if in_git_repo(link_abs.parent):
        names = [link_abs.name] + ([link_abs.name + ".html"] if made == "pointer" else [])
        try:
            ensure_gitignored(link_abs.parent, names)
            print(f"  (added {', '.join(names)} to {link_abs.parent / '.gitignore'} — it points outside the repo)")
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser(description="Drop a best-effort convenience symlink to a central post.")
    ap.add_argument("post_dir", help="the finished post in the central store (…/.paper2blogpost/posts/<slug>)")
    ap.add_argument("--at", help="where to put the pointer (default: ./<post-folder-name>)")
    args = ap.parse_args()
    raise SystemExit(publish(Path(args.post_dir), Path(args.at) if args.at else None))


if __name__ == "__main__":
    main()
