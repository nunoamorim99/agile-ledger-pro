#!/usr/bin/env python3
"""Agile-Ledger Pro — the local dashboard server.

Reads the ledger repo and serves it as a browsable, editable web page. Standard
library only: nothing to install, and it runs wherever Python 3.8+ does.

    python3 serve.py                     # find the ledger from the cwd
    python3 serve.py --ledger ~/Projetos/agile-ledger
    python3 serve.py --port 4173 --no-browser

It binds 127.0.0.1 only. The ledger is your team's product-management record,
and this server has no authentication, so it is never exposed to the network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agileledger import actions, commands, resolve  # noqa: E402
from agileledger.actions import ActionError  # noqa: E402
from agileledger.model import (ACTION_ROLES, BOARD_COLUMNS, BUG_STATE_LABEL,  # noqa: E402
                               BUG_STATES,
                               CONFIG_OWNERS, EPIC_STATE_LABEL, EPIC_STATES,
                               FIBONACCI, LAYERS, LEDGER_FILES, PRIORITIES,
                               PRIORITY_NAME, ROLE_NAME, ROLES, SEVERITIES,
                               STORY_STATE_LABEL, STORY_STATES)
from agileledger.store import Repo  # noqa: E402

STATIC = HERE / "static"
SAFE_SLUG = re.compile(r"^[A-Za-z0-9._-]+$")
CONTENT_TYPES = {".html": "text/html; charset=utf-8",
                 ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".svg": "image/svg+xml"}


class Workspace:
    """The resolved ledger root, shared by every request."""

    def __init__(self, root: Path):
        self.root = root
        self.lock = threading.Lock()

    def repo(self, slug: str) -> Repo:
        if not SAFE_SLUG.match(slug or ""):
            raise ActionError(f"invalid repo name: {slug!r}")
        return Repo(self.root, slug)

    def overview(self) -> dict:
        repos = []
        for row in resolve.list_repos(self.root):
            entry = dict(row)
            if row.get("present"):
                try:
                    entry["stats"] = self.repo(row["slug"]).snapshot()["stats"]
                except Exception as exc:            # a broken folder must not
                    entry["error"] = str(exc)       # hide the rest of the list
            repos.append(entry)
        return {
            "root": str(self.root),
            "config": resolve.read_config(self.root),
            # The team roster from Config.md. A list of names and roles, which
            # is all it is: see model.ROLES for why it is not a permission list.
            "team": resolve.read_team(self.root),
            # Who the person at *this* clone is, from the git-ignored
            # Me.local.md. Identity is the one setting that must not be
            # shared: see resolve.read_me.
            "me": resolve.read_me(self.root),
            "me_file": resolve.ME_FILE,
            "repos": repos,
            "git": actions.ledger_status(self.root),
            "vocabulary": {
                "story_states": STORY_STATES,
                "bug_states": BUG_STATES,
                "epic_states": EPIC_STATES,
                "board_columns": BOARD_COLUMNS,
                "priorities": [{"value": p, "name": PRIORITY_NAME[p]} for p in PRIORITIES],
                "severities": SEVERITIES,
                "layers": LAYERS,
                "fibonacci": FIBONACCI,
                "files": LEDGER_FILES,
                "roles": [{"value": r, "name": ROLE_NAME[r]} for r in ROLES],
                "config_owners": CONFIG_OWNERS,
                # Which roles run which action, for the dashboard to hide a
                # button the roster says is not this person's. A guardrail
                # and not a check that holds: see model.ACTION_ROLES.
                "action_roles": ACTION_ROLES,
                # The ledger's own words, emoji and all. The UI draws its own
                # glyphs but shows these on hover, so a reader can always get
                # back to the token that is actually written in the file — and
                # so "Ready" and "Delivered" stay distinguishable even though
                # the ledger spells both with a tick.
                "labels": {
                    "story": STORY_STATE_LABEL,
                    "bug": BUG_STATE_LABEL,
                    "epic": EPIC_STATE_LABEL,
                },
            },
        }

    def revision(self, slug: str) -> float:
        """Newest mtime in a repo folder, so the page can poll for changes."""
        folder = self.root / slug
        newest = 0.0
        for name in LEDGER_FILES:
            path = folder / name
            if path.is_file():
                newest = max(newest, path.stat().st_mtime)
        return newest


class Handler(BaseHTTPRequestHandler):
    server_version = "AgileLedgerPro"
    workspace: Workspace = None       # set on the server instance

    # -- plumbing ----------------------------------------------------------

    def log_message(self, fmt, *args):
        if self.server.verbose:
            sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # The page only ever talks to itself; no embedding, no sniffing.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    # -- routing -----------------------------------------------------------

    def do_GET(self):                                  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path.startswith("/static/"):
                return self._static(path[len("/static/"):])
            if path == "/api/workspace":
                return self._json(self.workspace.overview())
            if path == "/api/commands":
                return self._json(commands.sheet(HERE, set(actions.ACTIONS)))

            m = re.fullmatch(r"/api/repo/([^/]+)", path)
            if m:
                with self.workspace.lock:
                    data = self.workspace.repo(m.group(1)).snapshot()
                data["revision"] = self.workspace.revision(m.group(1))
                return self._json(data)

            m = re.fullmatch(r"/api/repo/([^/]+)/revision", path)
            if m:
                return self._json({"revision": self.workspace.revision(m.group(1))})

            m = re.fullmatch(r"/api/repo/([^/]+)/file/([^/]+)", path)
            if m:
                return self._raw_file(m.group(1), m.group(2))

            return self._error("not found", 404)
        except ActionError as exc:
            return self._error(str(exc))
        except FileNotFoundError as exc:
            return self._error(str(exc), 404)
        except Exception as exc:                        # never leak a traceback
            self.log_message("unhandled: %r", exc)
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    def do_POST(self):                                 # noqa: N802
        path = self.path.split("?", 1)[0]
        m = re.fullmatch(r"/api/repo/([^/]+)/action", path)
        if not m:
            return self._error("not found", 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                return self._error("request too large", 413)
            payload = json.loads(self.rfile.read(length) or b"{}")
            action = payload.get("action")
            params = payload.get("params") or {}
            if not isinstance(params, dict):
                return self._error("params must be an object")

            # One writer at a time: two browser tabs must not interleave edits.
            with self.workspace.lock:
                repo = self.workspace.repo(m.group(1))
                result = actions.run(repo, action, params)
                snapshot = repo.snapshot()
            snapshot["revision"] = self.workspace.revision(m.group(1))
            result["repo"] = snapshot
            return self._json(result)
        except ActionError as exc:
            return self._error(str(exc))
        except json.JSONDecodeError:
            return self._error("malformed JSON body")
        except FileNotFoundError as exc:
            return self._error(str(exc), 404)
        except Exception as exc:
            self.log_message("unhandled: %r", exc)
            return self._error(f"{type(exc).__name__}: {exc}", 500)

    # -- resources ---------------------------------------------------------

    def _static(self, name: str) -> None:
        target = (STATIC / name).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            return self._error("not found", 404)
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)

    def _raw_file(self, slug: str, name: str) -> None:
        if name not in LEDGER_FILES:
            return self._error("not a ledger file", 404)
        if not SAFE_SLUG.match(slug):
            return self._error("invalid repo name")
        path = self.workspace.root / slug / name
        if not path.is_file():
            return self._error("file not found", 404)
        self._json({"name": name, "text": path.read_text(encoding="utf-8")})


def build_server(root: Path, host: str, port: int, verbose: bool) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"workspace": Workspace(root)})
    server = ThreadingHTTPServer((host, port), handler)
    server.verbose = verbose
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="agile-ledger-pro dashboard",
        description="Browse and update an Agile-Ledger ledger in a local web page.")
    parser.add_argument("--ledger", metavar="PATH",
                        help="the ledger root (default: found from the current directory)")
    parser.add_argument("--port", type=int, default=4173, help="port (default: 4173)")
    parser.add_argument("--no-browser", action="store_true",
                        help="do not open a browser window")
    parser.add_argument("--verbose", action="store_true", help="log every request")
    args = parser.parse_args(argv)

    if args.ledger:
        root = Path(os.path.expanduser(args.ledger)).resolve()
        if not resolve.is_ledger_root(root):
            found = resolve.find_ledger_root(root)
            if not found:
                print(f"error: {root} is not a ledger root and none was found above it.\n"
                      f"       A ledger root holds a Registry.md starting with "
                      f"'# {resolve.REGISTRY_MARKER}'.\n"
                      f"       Run /init-ledger first, or pass --ledger <path>.",
                      file=sys.stderr)
                return 2
            root = found
    else:
        root = resolve.find_ledger_root(Path.cwd())
        if not root:
            print("error: no ledger found from this directory.\n"
                  "       Run the dashboard from your workspace, or pass "
                  "--ledger <path>.\n"
                  "       If you have no ledger yet, run /init-ledger in Claude Code.",
                  file=sys.stderr)
            return 2

    repos = [r["slug"] for r in resolve.list_repos(root)]
    try:
        server = build_server(root, "127.0.0.1", args.port, args.verbose)
    except OSError as exc:
        print(f"error: cannot listen on port {args.port}: {exc}\n"
              f"       Another dashboard may already be running — "
              f"try --port {args.port + 1}.", file=sys.stderr)
        return 2

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Agile-Ledger Pro dashboard")
    print(f"  ledger : {root}")
    print(f"  repos  : {', '.join(repos) if repos else '(none registered yet)'}")
    print(f"  serving: {url}  (local only)")
    print("  press Ctrl+C to stop")

    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
