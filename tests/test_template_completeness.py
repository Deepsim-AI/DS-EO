"""test_template_completeness.py — Checks all templates have required sections."""

import os
import unittest

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(PKG_ROOT, "templates")


class TestTemplateCompleteness(unittest.TestCase):

    # ─── Task Template ────────────────────────────────────────

    def test_task_template_has_naming_convention(self):
        content = self._read("task.md")
        self.assertTrue(
            any(term in content.lower() for term in ["task naming", "naming convention", "task_<"]),
            "task.md should contain TASK naming convention"
        )

    def test_task_template_has_directory_structure(self):
        content = self._read("task.md")
        self.assertIn("CTO_PLAN.md", content)
        self.assertIn("IMPLEMENTATION_REPORT.md", content)
        self.assertIn("REVIEW_REPORT.md", content)
        self.assertIn("CTO_APPROVAL.md", content)

    def test_task_template_has_handoff_artifacts(self):
        content = self._read("task.md")
        self.assertTrue(
            any(term in content.lower() for term in ["handoff", "artifact checklist", "phase"]),
            "task.md should contain handoff artifact information"
        )

    # ─── Report Template ──────────────────────────────────────

    def test_report_template_has_summary(self):
        content = self._read("report_template.md")
        self.assertIn("## Summary", content, "report_template.md missing 'Summary' section")

    def test_report_template_has_changes_made(self):
        content = self._read("report_template.md")
        self.assertIn("Changes Made", content, "report_template.md missing 'Changes Made' section")

    def test_report_template_has_acceptance_criteria_verification(self):
        content = self._read("report_template.md")
        self.assertTrue(
            any(term in content for term in ["Acceptance Criteria Verification", "acceptance criteria"]),
            "report_template.md should reference acceptance criteria verification"
        )

    def test_report_template_has_deviation_analysis(self):
        content = self._read("report_template.md")
        self.assertIn("Deviation Analysis", content, "report_template.md missing 'Deviation Analysis' section")

    # ─── Review Report Template ───────────────────────────────

    def test_review_report_has_summary(self):
        content = self._read("review_report_template.md")
        self.assertIn("## Review Summary", content, "review_report_template.md missing 'Review Summary'")

    def test_review_report_has_recommendation(self):
        content = self._read("review_report_template.md")
        self.assertTrue(
            any(term in content for term in ["Recommendation", "RECOMMENDATION"]),
            "review_report_template.md should have a Recommendation section"
        )

    def test_review_report_has_scoring_matrix(self):
        content = self._read("review_report_template.md")
        self.assertIn("Scoring Matrix", content, "review_report_template.md missing 'Scoring Matrix'")

    # ─── Spec Template ────────────────────────────────────────

    def test_spec_template_has_problem_statement(self):
        content = self._read("spec_template.md")
        self.assertIn("Problem Statement", content, "spec_template.md missing 'Problem Statement'")

    def test_spec_template_has_scope(self):
        content = self._read("spec_template.md")
        self.assertIn("Scope", content, "spec_template.md missing 'Scope' section")

    def test_spec_template_has_acceptance_criteria(self):
        content = self._read("spec_template.md")
        self.assertTrue(
            any(term in content for term in ["Acceptance Criteria", "acceptance criteria"]),
            "spec_template.md should reference acceptance criteria"
        )

    def test_spec_template_has_risks(self):
        content = self._read("spec_template.md")
        self.assertIn("Risks", content, "spec_template.md missing 'Risks' section")

    # ─── CTO Approval Template ──────────────────────────────

    def test_cto_approval_has_decision(self):
        content = self._read("cto_approval_template.md")
        self.assertTrue(
            any(term in content for term in ["APPROVE", "REJECT"]),
            "cto_approval_template.md should reference APPROVE/REJECT decision"
        )

    def test_cto_approval_has_rationale(self):
        content = self._read("cto_approval_template.md")
        self.assertIn("Rationale", content, "cto_approval_template.md missing 'Rationale' section")

    def test_cto_approval_has_two_layer_boundary_check(self):
        content = self._read("cto_approval_template.md")
        self.assertTrue(
            any(term in content.lower() for term in ["two-layer", "layer boundary", "development vs. runtime"]),
            "cto_approval_template.md should verify two-layer boundary"
        )

    # ─── No DS-AIOS References ──────────────────────────────

    def test_no_templates_have_ds_aios_references(self):
        """No template should contain DS-AIOS-specific path references."""
        for tpl in os.listdir(TEMPLATES_DIR):
            if not tpl.endswith(".md"):
                continue
            content = self._read(tpl)
            self.assertNotIn("agent_system/", content, f"{tpl} contains DS-AIOS path reference")


    # ─── Helper ──────────────────────────────────────────────

    def _read(self, filename):
        path = os.path.join(TEMPLATES_DIR, filename)
        with open(path, "r") as f:
            return f.read()


if __name__ == "__main__":
    unittest.main(verbosity=2)
