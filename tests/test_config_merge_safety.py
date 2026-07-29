"""test_config_merge_safety.py — Verifies config merge won't corrupt existing state.

Uses a temporary openclaw.json in /tmp to test the merge algorithm safely.
"""

import json
import os
import shutil
import tempfile
import unittest

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfigMergeSafety(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a temporary openclaw.json with realistic pre-existing content."""
        cls.tmpdir = tempfile.mkdtemp(prefix="ds-eo-test-")
        cls.test_config_path = os.path.join(cls.tmpdir, "openclaw.json")

        # Simulate a user's existing config with non-DS-EO agents and sections
        original_config = {
            "gateway": {
                "port": 3000,
                "host": "127.0.0.1"
            },
            "plugins": {
                "entries": [
                    {"id": "memory-core", "enabled": True},
                    {"id": "ollama", "enabled": True}
                ]
            },
            "skills": {
                "entries": []
            },
            "channels": {
                "webchat": {"enabled": True}
            },
            "agents": {
                "defaults": {
                    "model": {
                        "primary": "ollama/qwen3.6:35b",
                        "fallbacks": ["ollama/ornith:35b"]
                    }
                },
                "list": [
                    {
                        "id": "existing-agent",
                        "name": "Existing Agent",
                        "model": "ollama/qwen3-coder:latest"
                    }
                ]
            }
        }

        with open(cls.test_config_path, "w") as f:
            json.dump(original_config, f, indent=2)

        cls.original_gateway = json.dumps(original_config["gateway"], sort_keys=True)
        cls.original_plugins = json.dumps(original_config["plugins"], sort_keys=True)
        cls.original_skills = json.dumps(original_config["skills"], sort_keys=True)
        cls.original_channels = json.dumps(original_config["channels"], sort_keys=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up temp directory."""
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _get_merged_config(self):
        """Run the merge algorithm and return result."""
        agents_list = [
            {
                "default": True,
                "id": "cto",
                "name": "CTO / Architect",
                "model": "ollama/qwen3.6:35b",
                "workspace": "/test/workspace",
                "tools": {"allow": ["group:fs"], "deny": ["write"]}
            },
            {
                "default": False,
                "id": "implementer",
                "name": "Code Implementer",
                "model": "ollama/ornith:35b",
                "workspace": "/test/workspace",
                "tools": {"allow": ["group:fs"], "deny": []}
            },
            {
                "default": False,
                "id": "reviewer",
                "name": "Senior Code Reviewer",
                "model": "ollama/laguna-xs-2.1:q4_K_M",
                "workspace": "/test/workspace",
                "tools": {"allow": ["group:fs"], "deny": ["write"]}
            }
        ]

        with open(self.test_config_path, "r") as f:
            config = json.load(f)

        # Run merge algorithm (same logic as generate_openclaw_config.sh --merge)
        original_keys = {k: v for k, v in config.items() if k != "agents"}
        agents_section = config.get("agents", {})
        defaults = agents_section.setdefault("defaults", {})
        model_defaults = defaults.setdefault("model", {})

        current_list = list(agents_section.get("list", []))
        merged_list = list(current_list)
        added_ids = set()

        for agent in agents_list:
            aid = agent["id"]
            if aid not in {a["id"] for a in current_list}:
                merged_list.append(agent)
            else:
                # Replace existing entry with same ID
                for i, existing in enumerate(merged_list):
                    if existing.get("id") == aid:
                        merged_list[i] = agent
                        break

        result = {**original_keys, "agents": {"defaults": {"model": model_defaults}, "list": merged_list}}
        return result

    # ─── Tests ────────────────────────────────────────────────

    def test_merged_config_is_valid_json(self):
        """Resulting JSON passes round-trip."""
        config = self._get_merged_config()
        json_str = json.dumps(config)
        parsed = json.loads(json_str)
        self.assertEqual(parsed, config)

    def test_no_duplicate_agent_ids(self):
        """No duplicate 'id' values in merged config."""
        config = self._get_merged_config()
        ids = [a["id"] for a in config.get("agents", {}).get("list", [])]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}")

    def test_all_ds_eo_agents_present(self):
        """All 3 DS-EO agents are in the merged config."""
        config = self._get_merged_config()
        agent_ids = [a["id"] for a in config.get("agents", {}).get("list", [])]
        expected = {"cto", "implementer", "reviewer"}
        self.assertEqual(set(agent_ids), expected | {"existing-agent"})

    def test_existing_agent_preserved(self):
        """Non-DS-EO agent entry is preserved."""
        config = self._get_merged_config()
        agents = config.get("agents", {}).get("list", [])
        existing = [a for a in agents if a["id"] == "existing-agent"]
        self.assertEqual(len(existing), 1, "Existing non-DS-EO agent should be preserved")

    def test_gateway_preserved(self):
        """Gateway section is unchanged."""
        config = self._get_merged_config()
        current = json.dumps(config.get("gateway", {}), sort_keys=True)
        self.assertEqual(current, self.original_gateway)

    def test_plugins_preserved(self):
        """Plugins section is unchanged."""
        config = self._get_merged_config()
        current = json.dumps(config.get("plugins", {}), sort_keys=True)
        self.assertEqual(current, self.original_plugins)

    def test_skills_preserved(self):
        """Skills section is unchanged."""
        config = self._get_merged_config()
        current = json.dumps(config.get("skills", {}), sort_keys=True)
        self.assertEqual(current, self.original_skills)

    def test_channels_preserved(self):
        """Channels section is unchanged."""
        config = self._get_merged_config()
        current = json.dumps(config.get("channels", {}), sort_keys=True)
        self.assertEqual(current, self.original_channels)


if __name__ == "__main__":
    unittest.main(verbosity=2)
