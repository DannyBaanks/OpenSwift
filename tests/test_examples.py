import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from openswift.devices import DEVICES
from openswift.studio import make_server, sketch

ROOT = Path(__file__).resolve().parents[1]


class ExamplesTest(unittest.TestCase):
    def test_every_example_draws_without_problems(self) -> None:
        for path in sorted((ROOT / "examples").glob("*.swift")):
            data = sketch(path.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"], path.name)
            self.assertEqual(data["problems"], [], path.name)

    def test_every_device_draws(self) -> None:
        source = (ROOT / "examples" / "hello.swift").read_text(encoding="utf-8")
        for device_id in DEVICES:
            self.assertIn("<svg", sketch(source, device_id)["svg"], device_id)

    def test_studio_lists_devices_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            httpd = make_server(Path(tmp), port=0)
            port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                def get(route: str) -> dict:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}") as res:
                        return json.loads(res.read())

                ids = {d["id"] for d in get("/api/devices")["devices"]}
                self.assertEqual(ids, set(DEVICES))
                self.assertIsNone(get("/api/session")["session"])
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
