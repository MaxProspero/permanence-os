#!/usr/bin/env python3
"""Tests for skill registry."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.skill_registry as reg_mod  # noqa: E402


class TestExtractDocstring:
    def test_extracts_first_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            py_file = Path(tmp) / "test_script.py"
            py_file.write_text('#!/usr/bin/env python3\n"""First line of doc.\n\nMore details.\n"""\n', encoding="utf-8")
            result = reg_mod.SkillRegistry._extract_docstring(py_file)
            assert result == "First line of doc."

    def test_no_docstring(self):
        with tempfile.TemporaryDirectory() as tmp:
            py_file = Path(tmp) / "no_doc.py"
            py_file.write_text("import os\nx = 1\n", encoding="utf-8")
            result = reg_mod.SkillRegistry._extract_docstring(py_file)
            assert result == "No description"

    def test_single_quote_docstring(self):
        with tempfile.TemporaryDirectory() as tmp:
            py_file = Path(tmp) / "single.py"
            py_file.write_text("'''Single quote docstring.'''\n", encoding="utf-8")
            result = reg_mod.SkillRegistry._extract_docstring(py_file)
            assert result == "Single quote docstring."

    def test_missing_file(self):
        result = reg_mod.SkillRegistry._extract_docstring(Path("/nonexistent/file.py"))
        assert result == "No description"


class TestSkillRegistry:
    def test_scan_finds_scripts(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        skills = reg.list_skills(category="script")
        assert len(skills) > 10
        names = [s["name"] for s in skills]
        assert "idea_intake" in names

    def test_scan_finds_agents(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        skills = reg.list_skills(category="agent")
        assert len(skills) > 0

    def test_default_status_dormant(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        skills = reg.list_skills()
        for s in skills:
            assert s["status"] == "dormant"

    def test_activate_deactivate(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        skills = reg.list_skills(category="script")
        name = skills[0]["name"]
        assert reg.activate(name)
        assert reg.get_skill(name)["status"] == "active"
        assert reg.deactivate(name)
        assert reg.get_skill(name)["status"] == "dormant"

    def test_activate_nonexistent(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        assert not reg.activate("nonexistent_skill_xyz")

    def test_list_filter_category(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        scripts = reg.list_skills(category="script")
        agents = reg.list_skills(category="agent")
        all_skills = reg.list_skills()
        assert len(scripts) > 0
        assert len(agents) > 0
        assert len(all_skills) >= len(scripts) + len(agents)

    def test_list_filter_status(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        skills = reg.list_skills(category="script")
        reg.activate(skills[0]["name"])
        active = reg.list_skills(status="active")
        assert len(active) == 1
        dormant = reg.list_skills(status="dormant")
        assert len(dormant) < len(reg.list_skills())


class TestManifestRoundtrip:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            with patch.object(reg_mod, "MANIFEST_PATH", manifest_path):
                reg = reg_mod.SkillRegistry()
                reg.scan()
                skills = reg.list_skills(category="script")
                reg.activate(skills[0]["name"])
                reg.save_manifest()

                reg2 = reg_mod.SkillRegistry()
                reg2.load_manifest()
                reg2.scan()
                skill = reg2.get_skill(skills[0]["name"])
                assert skill["status"] == "active"


class TestHealthCheck:
    def test_existing_script(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        result = reg.health_check("idea_intake")
        assert result == "healthy"

    def test_nonexistent_skill(self):
        reg = reg_mod.SkillRegistry()
        reg.scan()
        result = reg.health_check("nonexistent_xyz")
        assert result == "not_found"


class TestWriteReport:
    def test_produces_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "outputs"
            with patch.object(reg_mod, "OUTPUT_DIR", out_dir):
                reg = reg_mod.SkillRegistry()
                reg.scan()
                report_path = reg_mod._write_report(reg)
                assert report_path.exists()
                content = report_path.read_text()
                assert "Skill Registry Report" in content
                assert "Total skills:" in content
