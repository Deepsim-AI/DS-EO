"""test_manifest_schema.py — Validates ds_eo_manifest.yaml against expected schema."""

import os
import re
import sys
import unittest

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed. Run: pip install pyyaml")
    sys.exit(1)


PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(PKG_ROOT, "ds_eo_manifest.yaml")


class TestManifestSchema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Load and parse the manifest once for all tests."""
        cls.assertTrue(os.path.isfile(MANIFEST_PATH), f"Manifest not found: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r") as f:
            cls.manifest = yaml.safe_load(f)

    # ─── Package Section ──────────────────────────────────────

    def test_package_name_present(self):
        name = self.manifest.get("package", {}).get("name")
        self.assertIsNotNone(name, "package.name is missing")
        self.assertIsInstance(name, str)
        self.assertTrue(len(name) > 0, "package.name must be non-empty")

    def test_package_version_semver(self):
        version = self.manifest.get("package", {}).get("version", "")
        self.assertRegex(version, r"^\d+\.\d+\.\d+$", f"Version '{version}' is not valid semver (MAJOR.MINOR.PATCH)")

    def test_package_license_present(self):
        license_id = self.manifest.get("package", {}).get("license", "")
        self.assertTrue(len(license_id) > 0, "package.license must be non-empty")

    def test_package_description_present(self):
        desc = self.manifest.get("package", {}).get("description", "")
        self.assertTrue(len(desc) > 0, "package.description must be non-empty")

    # ─── OpenClaw Section ────────────────────────────────────

    def test_openclaw_minimum_version(self):
        ver = self.manifest.get("openclaw", {}).get("minimum_version", "")
        self.assertRegex(ver, r"^\d+\.\d+\.\d+$", f"OpenClaw minimum_version '{ver}' is not valid")

    # ─── Roles Section ────────────────────────────────────────

    def test_roles_count(self):
        roles = self.manifest.get("roles", [])
        self.assertEqual(len(roles), 3, f"Expected exactly 3 roles, got {len(roles)}")

    def test_role_ids_present(self):
        role_ids = {r["id"] for r in self.manifest.get("roles", [])}
        expected = {"cto", "implementer", "reviewer"}
        self.assertEqual(role_ids, expected, f"Role IDs: got {role_ids}, expected {expected}")

    def test_each_role_has_required_fields(self):
        required = ["id", "name", "emoji", "prompt_file", "model_placeholder", "tool_profile", "default_model"]
        for role in self.manifest.get("roles", []):
            for field in required:
                self.assertIn(field, role, f"Role {role.get('id')} missing field: {field}")

    def test_prompt_files_reference_agents_dir(self):
        """Each role's prompt_file should reference agents/*.md."""
        for role in self.manifest.get("roles", []):
            pf = role["prompt_file"]
            self.assertTrue(pf.startswith("agents/"), f"Role {role['id']} prompt_file '{pf}' must start with 'agents/'")

    # ─── Protocols Section ──────────────────────────────────

    def test_protocols_count(self):
        protocols = self.manifest.get("protocols", [])
        self.assertEqual(len(protocols), 6, f"Expected exactly 6 protocols, got {len(protocols)}")

    def test_each_protocol_has_file_and_category(self):
        for proto in self.manifest.get("protocols", []):
            self.assertIn("file", proto, "Protocol missing 'file' field")
            self.assertIn("category", proto, "Protocol missing 'category' field")
            valid_cats = {"governance", "communication", "workflow"}
            self.assertIn(proto["category"], valid_cats, f"Invalid protocol category: {proto['category']}")

    # ─── Templates Section ──────────────────────────────────

    def test_templates_count(self):
        templates = self.manifest.get("templates", [])
        self.assertEqual(len(templates), 5, f"Expected exactly 5 templates, got {len(templates)}")

    def test_each_template_has_file_and_purpose(self):
        for tpl in self.manifest.get("templates", []):
            self.assertIn("file", tpl, "Template missing 'file' field")
            self.assertIn("purpose", tpl, "Template missing 'purpose' field")

    # ─── Installation Steps ──────────────────────────────────

    def test_installation_steps_count(self):
        steps = self.manifest.get("installation", {}).get("steps", [])
        self.assertEqual(len(steps), 7, f"Expected exactly 7 installation steps, got {len(steps)}")

    def test_installation_steps_sequential(self):
        steps = self.manifest.get("installation", {}).get("steps", [])
        step_nums = [s["step"] for s in steps]
        self.assertEqual(step_nums, list(range(1, 8)), "Steps must be numbered 1-7 sequentially")

    def test_step_2_is_interactive(self):
        steps = self.manifest.get("installation", {}).get("steps", [])
        step_2 = [s for s in steps if s["step"] == 2][0]
        self.assertTrue(step_2.get("interactive"), "Step 2 (generate config) must be interactive")

    # ─── No DS-AIOS References ──────────────────────────────

    def test_no_ds_aios_path_references(self):
        """Manifest should not contain hardcoded agent_system paths."""
        with open(MANIFEST_PATH, "r") as f:
            content = f.read()
        self.assertNotIn("agent_system", content, "Manifest contains DS-AIOS path reference 'agent_system'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
