"""
Unit tests for Server Guardian core modules.
"""

import unittest
import os
import tempfile
from pathlib import Path

from server_guardian.security import encrypt_secret, decrypt_secret
from server_guardian.config import GuardianConfig
from server_guardian.core.docker_manager import DockerManager
from server_guardian.ipc.protocol import create_request, parse_message, create_response


class TestServerGuardian(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["SERVER_GUARDIAN_DIR"] = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_encryption_and_decryption(self):
        plain = "SuperSecretPassword123!"
        encrypted = encrypt_secret(plain)
        self.assertNotEqual(plain, encrypted)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(plain, decrypted)

    def test_config_save_and_load(self):
        cfg = GuardianConfig.load()
        cfg.smtp.host = "smtp.custom.org"
        cfg.smtp.port = 465
        cfg.smtp.primary_email = "admin@example.com"
        cfg.smtp.backup_email = "backup@example.com"
        cfg.set_system_password("SysPassSecret")
        cfg.save()

        # Reload
        reloaded = GuardianConfig.load()
        self.assertEqual(reloaded.smtp.host, "smtp.custom.org")
        self.assertEqual(reloaded.smtp.port, 465)
        self.assertEqual(reloaded.smtp.primary_email, "admin@example.com")
        self.assertEqual(reloaded.smtp.backup_email, "backup@example.com")
        self.assertEqual(reloaded.get_system_password(), "SysPassSecret")

    def test_semver_tag_parsing(self):
        self.assertEqual(DockerManager.parse_semver_tag("1.2.3"), (1, 2, 3))
        self.assertEqual(DockerManager.parse_semver_tag("v2.0.4"), (2, 0, 4))
        self.assertEqual(DockerManager.parse_semver_tag("v3.1"), (3, 1, 0))
        self.assertIsNone(DockerManager.parse_semver_tag("latest"))
        self.assertIsNone(DockerManager.parse_semver_tag("alpine"))

    def test_ipc_protocol_serialization(self):
        req_bytes = create_request("ping", {"version": "1.0"})
        ok, parsed = parse_message(req_bytes)
        self.assertTrue(ok)
        self.assertEqual(parsed.get("action"), "ping")
        self.assertEqual(parsed.get("params", {}).get("version"), "1.0")

        resp_bytes = create_response(True, data={"metrics": 42})
        ok, parsed_resp = parse_message(resp_bytes)
        self.assertTrue(ok)
        self.assertTrue(parsed_resp.get("success"))
        self.assertEqual(parsed_resp.get("data", {}).get("metrics"), 42)


if __name__ == "__main__":
    unittest.main()
