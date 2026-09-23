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


def sketch(source: str) -> dict:
    try:
        root = parse_swiftui(source)
    except ParseError as exc:
        return {"ok": False, "error": str(exc), "svg": "", "problems": [str(exc)], "tree": None}
    problems: list[str] = []
    _problems(root, problems)
    return {
        "ok": True,
        "error": "",
        "svg": render_svg(root),
        "problems": problems,
        "tree": _tree(root),
        "tokens": highlight(source),
    }


def _safe(root: Path, raw: str) -> Path:
    path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != root and root not in path.parents:
        raise ValueError("path escapes the project")
    return path


def _files(root: Path) -> list[str]:
    skip = {".git", ".ui-session", "__pycache__", "node_modules"}
    found = []
    for path in root.rglob("*.swift"):
        if any(part in skip for part in path.parts):
            continue
        found.append(str(path.relative_to(root)))
    return sorted(found)


def serve(project: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    project = project.resolve()
    page = PAGE.read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            print(f"studio {self.address_string()} {fmt % args}")

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
            url = urlparse(self.path)
            if url.path == "/":
                body = page.replace("__PROJECT__", str(project)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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
            url = urlparse(self.path)
            data = self._read()
            if url.path == "/api/render":
                self._json(200, sketch(data.get("source", "")))
                return
            if url.path == "/api/save":
                try:
                    path = _safe(project, data.get("path", ""))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(data.get("text", ""), encoding="utf-8")
                    self._json(200, {"ok": True})
                except (OSError, ValueError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            self._json(404, {"error": "not found"})

    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}")
    httpd.serve_forever()
