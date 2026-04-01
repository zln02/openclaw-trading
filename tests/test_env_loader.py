"""Regression tests for shared OpenClaw env/path loading."""
from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class EnvLoaderTests(unittest.TestCase):
    def test_parse_env_file_treats_values_as_data(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env_path = Path(td) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "SAFE_KEY=value",
                        "export QUOTED='hello world'",
                        "INLINE_COMMENT=keep # comment",
                        "INVALID-KEY=skip-me",
                        "DANGEROUS=$(touch /tmp/should_not_run)",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                env_loader = importlib.import_module("common.env_loader")
                parsed = env_loader._parse_env_file(env_path)

        self.assertEqual(parsed["SAFE_KEY"], "value")
        self.assertEqual(parsed["QUOTED"], "hello world")
        self.assertEqual(parsed["INLINE_COMMENT"], "keep")
        self.assertEqual(parsed["DANGEROUS"], "$(touch /tmp/should_not_run)")
        self.assertNotIn("INVALID-KEY", parsed)

    def test_load_env_uses_env_configured_paths_and_json_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "state"
            workspace = root / "workspace"
            skill_dir = workspace / "skills" / "kiwoom-api"
            secrets_dir = workspace / ".docker-secrets"
            workspace.mkdir(parents=True)
            skill_dir.mkdir(parents=True)
            secrets_dir.mkdir(parents=True)
            (root / ".env").write_text("ROOT_ONLY=root\nSHARED=from-root\n", encoding="utf-8")
            (workspace / ".env").write_text("WORK_ONLY=workspace\nSHARED=from-workspace\n", encoding="utf-8")
            (skill_dir / ".env").write_text("SKILL_ONLY=skill\n", encoding="utf-8")
            (secrets_dir / "SUPABASE_URL").write_text("https://example.supabase.co", encoding="utf-8")
            (secrets_dir / "SUPABASE_SECRET_KEY").write_text("secret-from-docker-secrets", encoding="utf-8")
            config_path = root / "openclaw.json"
            config_path.write_text(
                json.dumps(
                    {
                        "env": {"JSON_ONLY": "json-value"},
                        "channels": {"telegram": {"botToken": "telegram-from-json"}},
                    }
                ),
                encoding="utf-8",
            )

            env = {
                "OPENCLAW_CONFIG_DIR": str(root),
                "OPENCLAW_WORKSPACE_DIR": str(workspace),
                "OPENCLAW_CONFIG_PATH": str(config_path),
            }
            with patch.dict(os.environ, env, clear=True):
                config = importlib.import_module("common.config")
                config = importlib.reload(config)
                env_loader = importlib.import_module("common.env_loader")
                env_loader = importlib.reload(env_loader)
                env_loader.load_env()

                self.assertEqual(config.OPENCLAW_ROOT, root)
                self.assertEqual(config.WORKSPACE, workspace)
                self.assertEqual(os.environ["ROOT_ONLY"], "root")
                self.assertEqual(os.environ["WORK_ONLY"], "workspace")
                self.assertEqual(os.environ["SKILL_ONLY"], "skill")
                self.assertEqual(os.environ["JSON_ONLY"], "json-value")
                self.assertEqual(os.environ["SHARED"], "from-root")
                self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "telegram-from-json")
                self.assertEqual(os.environ["SUPABASE_URL"], "https://example.supabase.co")
                self.assertEqual(os.environ["SUPABASE_SECRET_KEY"], "secret-from-docker-secrets")


if __name__ == "__main__":
    unittest.main()
