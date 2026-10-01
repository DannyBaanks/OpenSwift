"""Local studio: files, source, phone sketch, and a panel. No Swift compiler."""

from __future__ import annotations

import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from openswift.parse import ParseError, ViewNode, parse_swiftui
from openswift.render import render_svg

PAGE = Path(__file__).with_name("studio.html")
KNOWN = {"VStack", "HStack", "ZStack", "Text", "Button", "Spacer", "Divider", "TextField", "SecureField", "Image", "Label"}


def _tree(node: ViewNode) -> dict:
    return {
        "kind": node.kind,
        "text": node.text,
        "notes": node.notes,
        "children": [_tree(child) for child in node.children],
    }


def _problems(node: ViewNode, found: list[str]) -> None:
    if node.kind not in KNOWN:
        found.append(f"{node.kind} is not drawn; it shows as a labeled box")
    for note in node.notes:
        found.append(f".{note} is ignored")
    for child in node.children:
        _problems(child, found)


def highlight(source: str) -> list:
    exe = Path(__file__).resolve().parents[1] / "bin" / "openswift-lex"
    if not exe.is_file():
        return []
    proc = subprocess.run([str(exe)], input=source.encode(), capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


def sketch(source: str, device: str = "iphone-14") -> dict:
    try:
        root = parse_swiftui(source)
    except ParseError as exc:
        return {"ok": False, "error": str(exc), "svg": "", "problems": [str(exc)], "tree": None}
    problems: list[str] = []
    _problems(root, problems)
    return {
        "ok": True,
        "error": "",
        "svg": render_svg(root, device),
        "problems": problems,
        "tree": _tree(root),
        "tokens": highlight(source),
        "device": device,
    }


def _safe(root: Path, raw: str) -> Path:
    path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path escapes the project")
    return path


def _session_allows_write(root: Path, path: Path) -> bool:
    """Honor an active .ui-session as the write boundary for Studio."""
    session = root / ".ui-session" / "target.json"
    if not session.is_file():
        return True
    record = json.loads(session.read_text(encoding="utf-8"))
    writable = record.get("writable_paths")
    if writable is None:
        target = Path(record["target"]).resolve()
        writable = [str(target)]
        writable.extend(str((target.parent / item).resolve()) for item in record.get("allowed", []))
    resolved = path.resolve()
    return any(resolved == Path(item).resolve() for item in writable)


def _files(root: Path) -> list[str]:
    skip = {".git", ".ui-session", "__pycache__", "node_modules"}
    found = []
    for path in root.rglob("*.swift"):
        if any(part in skip for part in path.parts):
            continue
        found.append(str(path.relative_to(root)))
    return sorted(found)


def request_refusal(method: str, headers, allowed_hosts: set[str]) -> str | None:
    """Why a request must be refused, or None.

    The studio can write files, so any web page the user has open must not be
    able to drive it. Host blocks DNS rebinding; Origin blocks cross-site
    requests; requiring a JSON body on POST forces a CORS preflight, which this
    server never answers, so a plain form or text/plain POST cannot get in.
    """
    host = (headers.get("Host") or "").lower()
    if host not in allowed_hosts:
        return "unexpected Host"
    origin = headers.get("Origin")
    if origin is not None and urlparse(origin).netloc.lower() not in allowed_hosts:
        return "cross-origin request"
    if method == "POST":
        ctype = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return "POST body must be application/json"
    return None


def make_server(project: Path, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    project = project.resolve()
    page = PAGE.read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"studio {self.address_string()} {fmt % args}")

        def _refused(self, method: str) -> bool:
            reason = request_refusal(method, self.headers, self.server.allowed_hosts)
            if reason:
                self._json(403, {"error": reason})
                return True
            return False

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if not length:
                return {}
            return json.loads(self.rfile.read(length).decode())

        def do_GET(self) -> None:  # noqa: N802
            if self._refused("GET"):
                return
            url = urlparse(self.path)
            if url.path == "/":
                body = page.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                )
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if url.path == "/api/files":
                self._json(200, {"root": str(project), "files": _files(project)})
                return
            if url.path == "/api/file":
                rel = parse_qs(url.query).get("path", [""])[0]
                try:
                    path = _safe(project, rel)
                    self._json(200, {"path": rel, "text": path.read_text(encoding="utf-8")})
                except (OSError, ValueError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self._refused("POST"):
                return
            url = urlparse(self.path)
            try:
                data = self._read()
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "body is not JSON"})
                return
            if url.path == "/api/render":
                device = data.get("device", "iphone-14")
                self._json(200, sketch(data.get("source", ""), device))
                return
            if url.path == "/api/save":
                try:
                    path = _safe(project, data.get("path", ""))
                    if not _session_allows_write(project, path):
                        self._json(403, {"error": "file is read-only in active .ui-session"})
                        return
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(data.get("text", ""), encoding="utf-8")
                    self._json(200, {"ok": True})
                except (OSError, ValueError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            self._json(404, {"error": "not found"})

    httpd = ThreadingHTTPServer((host, port), Handler)
    bound = httpd.server_address[1]
    httpd.allowed_hosts = {f"{name}:{bound}" for name in {host, "127.0.0.1", "localhost"}}
    return httpd


def serve(project: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = make_server(project, host, port)
    print(f"http://{host}:{httpd.server_address[1]}")
    httpd.serve_forever()
