"""End-to-end test: real MCP stdio server process against a fake Odoo JSON-RPC endpoint.

Run: python3 -m unittest discover -s claude-plugins/odoo-ngocvietai/tests
"""

import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "server" / "odoo_mcp.py"

PARTNERS = [
    {"id": 1, "name": "Ngọc Việt AI", "email": "info@ngocvietai.com", "image_1920": "AAAA"},
    {"id": 2, "name": "ACME", "email": "acme@example.com", "image_1920": "BBBB"},
]


class FakeOdoo(BaseHTTPRequestHandler):
    calls: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        # Mirror the odoo.ngocvietai.com WAF, which rejects Python's default User-Agent.
        if self.headers.get("User-Agent", "").startswith("Python-urllib"):
            self.send_response(403)
            self.end_headers()
            return
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        p = req["params"]
        FakeOdoo.calls.append((p["service"], p["method"], p["args"]))
        result, error = None, None
        if (p["service"], p["method"]) == ("common", "version"):
            result = {"server_version": "16.0"}
        elif (p["service"], p["method"]) == ("common", "authenticate"):
            db, login, key, _ = p["args"]
            result = 7 if (db, login, key) == ("prod", "bot@ngocvietai.com", "secret") else False
        elif p["service"] == "object":
            db, uid, key, model, method, args, kwargs = p["args"]
            assert (db, uid, key) == ("prod", 7, "secret")
            if method == "fields_get":
                result = {"id": {"type": "integer"}, "name": {"type": "char"},
                          "email": {"type": "char"}, "image_1920": {"type": "binary"}}
            elif method == "search_read":
                fields = kwargs["fields"]
                result = [{k: r[k] for k in fields} for r in PARTNERS][: kwargs["limit"]]
            elif method == "create":
                error = {"message": "Odoo Server Error", "data": {"message": "You are not allowed to create"}}
        body = {"jsonrpc": "2.0", "id": req["id"]}
        body.update({"error": error} if error else {"result": result})
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class OdooMcpE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeOdoo)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def start(self, **extra_env):
        env = {k: v for k, v in os.environ.items() if not k.startswith("ODOO_")}
        env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
                   ODOO_URL=self.url, ODOO_DB="prod", ODOO_USERNAME="bot@ngocvietai.com",
                   ODOO_API_KEY="secret")
        env.update(extra_env)
        proc = subprocess.Popen([sys.executable, "-I", str(SERVER)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, env=env)
        self.addCleanup(self._stop, proc)
        self._next = 0

        def rpc(method, params=None):
            self._next += 1
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self._next, "method": method,
                                         "params": params or {}}) + "\n")
            proc.stdin.flush()
            reply = json.loads(proc.stdout.readline())
            self.assertEqual(reply["id"], self._next)
            return reply

        init = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "test", "version": "0"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        return rpc

    @staticmethod
    def _stop(proc):
        proc.stdin.close()
        proc.wait(timeout=10)
        proc.stdout.close()

    def call(self, rpc, name, args):
        res = rpc("tools/call", {"name": name, "arguments": args})["result"]
        return res["isError"], res["content"][0]["text"]

    def test_search_read_authenticates_and_omits_binary_fields_by_default(self):
        # Unset login-form fields arrive as empty strings and must fall back to ODOO_* env vars.
        rpc = self.start(ODOO_CONFIG_DB="", ODOO_CONFIG_USERNAME="", ODOO_CONFIG_API_KEY="")
        is_err, text = self.call(rpc, "odoo_search_read", {"model": "res.partner", "limit": 5})
        self.assertFalse(is_err, text)
        records = json.loads(text)["records"]
        self.assertEqual([r["name"] for r in records], [p["name"] for p in PARTNERS])
        self.assertTrue(all("image_1920" not in r for r in records))

    def test_read_only_by_default_and_write_mode_never_deletes_or_touches_accounting(self):
        """Policy from decision 6 in ODOO_NGU_CANH_HIEN_TAI: read-only, no delete, no accounting edits."""
        write_tools = {"odoo_create", "odoo_write", "odoo_call_method"}
        ro = self.start()
        names = {t["name"] for t in ro("tools/list")["result"]["tools"]}
        self.assertIn("odoo_search_read", names)
        self.assertFalse(names & (write_tools | {"odoo_unlink"}))
        is_err, _ = self.call(ro, "odoo_write", {"model": "res.partner", "ids": [2], "values": {"name": "x"}})
        self.assertTrue(is_err)

        rw = self.start(ODOO_ALLOW_WRITE="1")
        names = {t["name"] for t in rw("tools/list")["result"]["tools"]}
        self.assertTrue(write_tools <= names)
        self.assertNotIn("odoo_unlink", names)
        FakeOdoo.calls.clear()
        refused = [
            ("odoo_call_method", {"model": "res.partner", "method": "unlink", "args": [[2]]}),
            ("odoo_write", {"model": "account.move", "ids": [1], "values": {"ref": "x"}}),
            ("odoo_call_method", {"model": "account.move", "method": "action_post", "args": [[1]]}),
        ]
        for name, args in refused:
            is_err, text = self.call(rw, name, args)
            self.assertTrue(is_err, (name, text))
        self.assertFalse([c for c in FakeOdoo.calls if c[0] == "object"],
                         "refused calls must not reach Odoo")
        # Errors raised by Odoo itself still come back as tool errors.
        is_err, text = self.call(rw, "odoo_create", {"model": "res.partner", "values": {"name": "x"}})
        self.assertTrue(is_err)
        self.assertIn("not allowed to create", text)

    def test_login_form_values_take_precedence_and_bad_credentials_fail(self):
        # The plugin login form (ODOO_CONFIG_*) wins over environment variables.
        rpc = self.start(ODOO_CONFIG_API_KEY="wrong")
        is_err, text = self.call(rpc, "odoo_server_info", {})
        self.assertTrue(is_err)
        self.assertIn("Authentication failed", text)


if __name__ == "__main__":
    unittest.main()
