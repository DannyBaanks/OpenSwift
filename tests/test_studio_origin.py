import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from openswift.studio import make_server


class StudioOriginTest(unittest.TestCase):
    """Only the studio page itself may drive the studio server."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        (self.project / "A.swift").write_text("struct A {}\n", encoding="utf-8")
        (self.project / "B.swift").write_text("struct B {}\n", encoding="utf-8")
        (self.project / "C.swift").write_text("struct C {}\n", encoding="utf-8")
        self.httpd = make_server(self.project, port=0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=json.dumps(body).encode() if body is not None else None,
                     headers=headers or {})
        res = conn.getresponse()
        data = json.loads(res.read() or b"{}")
        conn.close()
        return res.status, data

    def save(self, headers: dict) -> tuple[int, dict]:
        return self.request("POST", "/api/save", {"path": "pwned.txt", "text": "x"}, headers)

    def test_studio_page_can_save(self) -> None:
        status, _ = self.save({"Content-Type": "application/json",
                               "Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        self.assertTrue((self.project / "pwned.txt").exists())

    def test_foreign_origin_cannot_save(self) -> None:
        status, _ = self.save({"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        self.assertFalse((self.project / "pwned.txt").exists())

    def test_text_plain_post_cannot_save(self) -> None:
        # the exact request a web page can send without a CORS preflight
        status, _ = self.save({"Content-Type": "text/plain"})
        self.assertEqual(status, 403)
        self.assertFalse((self.project / "pwned.txt").exists())

    def test_rebound_host_cannot_read(self) -> None:
        # DNS rebinding: evil.example resolves to 127.0.0.1, so the page is same-origin
        status, data = self.request("GET", "/api/file?path=A.swift",
                                    headers={"Host": f"evil.example:{self.port}"})
        self.assertEqual(status, 403)
        self.assertNotIn("text", data)

    def test_localhost_can_read(self) -> None:
        status, data = self.request("GET", "/api/file?path=A.swift",
                                    headers={"Host": f"localhost:{self.port}"})
        self.assertEqual(status, 200)
        self.assertEqual(data["text"], "struct A {}\n")

    def test_bad_json_is_400_not_a_crash(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/render", body=b"{not json", headers={"Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 400)
        conn.close()

    def test_active_session_enforces_target_and_allowed(self) -> None:
        session = self.project / ".ui-session"
        session.mkdir()
        (session / "target.json").write_text(json.dumps({
            "target": str(self.project / "A.swift"),
            "allowed": ["B.swift"],
            "writable_paths": [str(self.project / "A.swift"), str(self.project / "B.swift")],
        }), encoding="utf-8")
        headers = {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}

        status, _ = self.request("POST", "/api/save", {"path": "A.swift", "text": "target\n"}, headers)
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/api/save", {"path": "B.swift", "text": "allowed\n"}, headers)
        self.assertEqual(status, 200)
        status, data = self.request("POST", "/api/save", {"path": "C.swift", "text": "blocked\n"}, headers)
        self.assertEqual(status, 403)
        self.assertIn("read-only", data["error"])
        self.assertEqual((self.project / "C.swift").read_text(encoding="utf-8"), "struct C {}\n")


if __name__ == "__main__":
    unittest.main()
