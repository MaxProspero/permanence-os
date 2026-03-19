"""Tests for scripts/oca_proposal_generator.py -- OCA proposal generation with voice compliance."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import oca_proposal_generator as pg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_lead(**overrides) -> dict:
    defaults = {"name": "Bobs HVAC", "industry": "hvac"}
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Workflow catalog
# ---------------------------------------------------------------------------

class TestWorkflowCatalog:
    def test_catalog_has_five_workflows(self):
        assert len(pg.WORKFLOW_CATALOG) == 5

    def test_all_workflows_have_required_keys(self):
        required = {"name", "description", "deliverables", "timeline", "pricing"}
        for wid, workflow in pg.WORKFLOW_CATALOG.items():
            missing = required - set(workflow.keys())
            assert not missing, f"{wid} missing: {missing}"

    def test_all_workflows_have_pricing_components(self):
        for wid, workflow in pg.WORKFLOW_CATALOG.items():
            assert "setup" in workflow["pricing"], f"{wid} missing setup price"
            assert "monthly" in workflow["pricing"], f"{wid} missing monthly price"
            assert workflow["pricing"]["setup"] > 0
            assert workflow["pricing"]["monthly"] > 0

    def test_all_workflows_have_deliverables(self):
        for wid, workflow in pg.WORKFLOW_CATALOG.items():
            assert len(workflow["deliverables"]) >= 3, f"{wid} has too few deliverables"

    def test_list_workflows(self):
        workflows = pg.list_workflows()
        assert len(workflows) == 5
        for w in workflows:
            assert "id" in w
            assert "name" in w
            assert "setup_cost" in w
            assert "monthly_cost" in w


# ---------------------------------------------------------------------------
# Voice compliance
# ---------------------------------------------------------------------------

class TestVoiceCompliance:
    def test_clean_text_passes(self):
        text = "This automation handles invoice triage. The system runs daily."
        violations = pg.check_voice_compliance(text)
        assert violations == []

    def test_hype_language_detected(self):
        text = "This amazing revolutionary system will change everything."
        violations = pg.check_voice_compliance(text)
        assert len(violations) > 0
        rules = [v["rule"] for v in violations]
        assert "Hype language" in rules

    def test_cheerleading_detected(self):
        text = "Let's go! We are crushing it with this automation."
        violations = pg.check_voice_compliance(text)
        rules = [v["rule"] for v in violations]
        assert "Cheerleading" in rules

    def test_multiple_exclamation_marks(self):
        text = "This is great!! We will deliver!!"
        violations = pg.check_voice_compliance(text)
        rules = [v["rule"] for v in violations]
        assert "Multiple exclamation marks" in rules

    def test_excessive_hedging_detected(self):
        text = "I think maybe this could possibly be useful."
        violations = pg.check_voice_compliance(text)
        rules = [v["rule"] for v in violations]
        assert "Excessive hedging" in rules


# ---------------------------------------------------------------------------
# Proposal generation
# ---------------------------------------------------------------------------

class TestProposalGeneration:
    def test_generates_for_valid_workflow(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert result["ok"] is True
        assert result["workflow_id"] == "lead_gen"

    def test_rejects_unknown_workflow(self):
        result = pg.generate_proposal(_sample_lead(), "nonexistent")
        assert result["ok"] is False
        assert "Unknown workflow" in result["error"]

    def test_markdown_contains_required_sections(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        md = result["markdown"]
        assert "## Executive Summary" in md
        assert "## What We Build" in md
        assert "## Timeline" in md
        assert "## Pricing" in md
        assert "## How It Works" in md
        assert "## Terms" in md

    def test_markdown_contains_lead_name(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(name="Acme Plumbing"), "lead_gen", output_dir=tmp_path,
        )
        assert "Acme Plumbing" in result["markdown"]

    def test_markdown_contains_pricing_table(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert "$500" in result["markdown"]
        assert "$200" in result["markdown"]

    def test_custom_notes_appended(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(),
            "lead_gen",
            custom_notes="Priority deployment requested.",
            output_dir=tmp_path,
        )
        assert "Priority deployment requested." in result["markdown"]
        assert "## Additional Notes" in result["markdown"]

    def test_voice_compliance_on_output(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert result["voice_compliant"] is True
        assert result["voice_violations"] == []

    def test_word_count_positive(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert result["word_count"] > 50

    def test_all_workflows_generate_valid_proposals(self, tmp_path):
        for wid in pg.WORKFLOW_CATALOG:
            result = pg.generate_proposal(
                _sample_lead(), wid, output_dir=tmp_path,
            )
            assert result["ok"] is True, f"Failed for {wid}"
            assert result["voice_compliant"] is True, f"Voice violation in {wid}"

    def test_all_proposals_voice_compliant(self, tmp_path):
        """Every generated proposal must pass voice compliance -- no exceptions."""
        for wid in pg.WORKFLOW_CATALOG:
            result = pg.generate_proposal(
                _sample_lead(name=f"Client {wid}"), wid, output_dir=tmp_path,
            )
            violations = result["voice_violations"]
            assert violations == [], (
                f"Workflow {wid} produced voice violations: {violations}"
            )


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

class TestFileOutput:
    def test_creates_markdown_file(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert result["md_path"]
        assert os.path.exists(result["md_path"])

    def test_creates_json_file(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        assert result["json_path"]
        assert os.path.exists(result["json_path"])

    def test_json_file_parseable(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "lead_gen", output_dir=tmp_path,
        )
        with open(result["json_path"]) as f:
            data = json.load(f)
        assert data["ok"] is True
        assert data["workflow_id"] == "lead_gen"

    def test_filename_sanitizes_lead_name(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(name="Bob's HVAC & Plumbing!"), "lead_gen", output_dir=tmp_path,
        )
        path = result["md_path"]
        filename = os.path.basename(path)
        assert "'" not in filename
        assert "&" not in filename
        assert "!" not in filename

    def test_result_has_metadata(self, tmp_path):
        result = pg.generate_proposal(
            _sample_lead(), "appointment_booking", output_dir=tmp_path,
        )
        assert result["pricing"]["setup"] == 750
        assert result["pricing"]["monthly"] == 300
        assert result["timeline"] == "7 days"
        assert "generated_at" in result
