"""test_protocol_extraction.py — Verifies all core protocols are present and properly genericized."""

import os
import re
import unittest

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTOCOLS_DIR = os.path.join(PKG_ROOT, "protocols")

REQUIRED_PROTOCOLS = [
    "approval_protocol.md",
    "communication_protocol.md",
    "completion_protocol.md",
    "delegation_protocol.md",
    "handoff_protocol.md",
    "review_protocol.md",
]


class TestProtocolExtraction(unittest.TestCase):

    # ─── File Existence & Size ────────────────────────────────

    def test_all_protocol_files_exist(self):
        for proto in REQUIRED_PROTOCOLS:
            path = os.path.join(PROTOCOLS_DIR, proto)
            self.assertTrue(os.path.isfile(path), f"Protocol missing: {proto}")

    def test_all_protocols_non_empty(self):
        for proto in REQUIRED_PROTOCOLS:
            path = os.path.join(PROTOCOLS_DIR, proto)
            size = os.path.getsize(path)
            self.assertGreater(size, 500, f"{proto} is too small ({size} bytes) — may be truncated")

    # ─── Gate Definitions Present ─────────────────────────────

    def test_approval_protocol_has_gates(self):
        content = self._read("approval_protocol.md")
        for gate in ["G1", "G2", "G3", "G4"]:
            self.assertIn(gate, content, f"Gate {gate} not found in approval_protocol.md")

    def test_completion_protocol_has_gate_references(self):
        content = self._read("completion_protocol.md")
        # Should reference Gate G2 and G4 at minimum
        gates_found = re.findall(r"Gate G[1-4]", content)
        self.assertTrue(len(gates_found) >= 2, "completion_protocol.md should reference at least 2 gates")

    def test_handoff_protocol_has_gate_references(self):
        content = self._read("handoff_protocol.md")
        gates_found = re.findall(r"Gate G[1-4]", content)
        self.assertTrue(len(gates_found) >= 3, "handoff_protocol.md should reference at least 3 gates")

    # ─── No DS-AIOS-Specific References ──────────────────────

    def test_no_agent_system_path_references(self):
        """No protocol file should contain 'agent_system/' path references."""
        for proto in REQUIRED_PROTOCOLS:
            content = self._read(proto)
            self.assertNotIn("agent_system/", content, f"{proto} contains DS-AIOS path reference 'agent_system/'")

    def test_no_ceo_agent_reference(self):
        """Protocols should not define CEO Agent as a role."""
        for proto in REQUIRED_PROTOCOLS:
            content = self._read(proto)
            # Should not have "CEO Agent" as a defined role in protocol context
            if "CEO" in content:
                self.assertIn("runtime", content, f"{proto} references 'CEO' but not in runtime context")

    def test_no_research_writer_agent_references(self):
        """Protocols should not reference Research or Writer agents."""
        for proto in REQUIRED_PROTOCOLS:
            content = self._read(proto)
            self.assertNotIn("Research Agent", content, f"{proto} references 'Research Agent' (DS-AIOS specific)")
            self.assertNotIn("Writer Agent", content, f"{proto} references 'Writer Agent' (DS-AIOS specific)")

    def test_no_hardcoded_host_paths(self):
        """No protocol should contain hardcoded host paths like /home/deepsim/."""
        for proto in REQUIRED_PROTOCOLS:
            content = self._read(proto)
            self.assertNotIn("/home/deepsim/", content, f"{proto} contains hardcoded host path")

    def test_has_ds_eo_scope_header(self):
        """Each protocol should indicate it's a DS-EO edition."""
        for proto in REQUIRED_PROTOCOLS:
            content = self._read(proto)
            # Should reference "DS-EO" or "OpenClaw Edition" somewhere
            has_reference = ("DS-EO" in content or "OpenClaw Edition" in content or
                           "Global Standard" in content or "all OpenClaw" in content)
            self.assertTrue(has_reference, f"{proto} lacks DS-EO scope indicator")

    # ─── Helper ──────────────────────────────────────────────

    def _read(self, filename):
        path = os.path.join(PROTOCOLS_DIR, filename)
        with open(path, "r") as f:
            return f.read()


if __name__ == "__main__":
    unittest.main(verbosity=2)
