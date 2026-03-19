"""Tests for scripts/oca_lead_generator.py -- OCA lead scraping and scoring pipeline."""

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import oca_lead_generator as lg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_lead(**overrides) -> dict:
    """Create a sample lead dict for testing."""
    defaults = {
        "name": "Test Biz",
        "industry": "restaurants",
        "website": "",
        "email": "test@example.com",
        "phone": "555-0100",
        "city": "Fayetteville",
        "state": "AR",
        "source": "test",
        "description": "small business local restaurant",
        "size_indicator": "small",
    }
    defaults.update(overrides)
    return lg.make_lead(**defaults)


def _sample_config(**overrides) -> dict:
    """Return a config dict for testing."""
    cfg = lg.DEFAULT_CONFIG.copy()
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# make_lead
# ---------------------------------------------------------------------------

class TestMakeLead:
    def test_returns_dict(self):
        lead = lg.make_lead("Acme Corp")
        assert isinstance(lead, dict)

    def test_lead_id_format(self):
        lead = lg.make_lead("Acme Corp", city="Fayetteville", state="AR")
        assert lead["lead_id"].startswith("L-")
        assert len(lead["lead_id"]) == 14  # "L-" + 12 hex

    def test_lead_id_deterministic(self):
        a = lg.make_lead("Acme Corp", city="Fayetteville", state="AR")
        b = lg.make_lead("Acme Corp", city="Fayetteville", state="AR")
        assert a["lead_id"] == b["lead_id"]

    def test_lead_id_case_insensitive(self):
        a = lg.make_lead("ACME CORP", city="FAYETTEVILLE", state="AR")
        b = lg.make_lead("acme corp", city="fayetteville", state="AR")
        assert a["lead_id"] == b["lead_id"]

    def test_different_leads_different_ids(self):
        a = lg.make_lead("Acme Corp", city="Fayetteville", state="AR")
        b = lg.make_lead("Beta LLC", city="Fayetteville", state="AR")
        assert a["lead_id"] != b["lead_id"]

    def test_initial_score_zero(self):
        lead = lg.make_lead("Test")
        assert lead["score"] == 0
        assert lead["score_breakdown"] == {}

    def test_strips_whitespace_from_name(self):
        lead = lg.make_lead("  Acme Corp  ")
        assert lead["name"] == "Acme Corp"

    def test_scanned_at_present(self):
        lead = lg.make_lead("Test")
        assert "scanned_at" in lead
        assert "T" in lead["scanned_at"]  # ISO format


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_base_score_is_50(self):
        lead = lg.make_lead("Neutral Biz")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        # Base 50 + 10 (no website) = 60
        assert scored["score"] == 60

    def test_industry_match_bonus(self):
        lead = lg.make_lead("Pizza Place", industry="restaurants")
        config = _sample_config(target_industries=["restaurants"])
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("industry_match") == 15

    def test_industry_match_case_insensitive(self):
        lead = lg.make_lead("Pizza Place", industry="Restaurants")
        config = _sample_config(target_industries=["restaurants"])
        scored = lg.score_lead(lead, config)
        assert "industry_match" in scored["score_breakdown"]

    def test_website_present_bonus(self):
        lead = lg.make_lead("Biz", website="https://example.com")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("has_website") == 5

    def test_no_website_higher_bonus(self):
        lead = lg.make_lead("Biz", website="")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("no_website_needs_help") == 10

    def test_keyword_matches(self):
        lead = lg.make_lead("Local Restaurant", description="small business scheduling")
        config = _sample_config(target_keywords=["small business", "scheduling", "local"])
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("keyword_matches", 0) > 0

    def test_keyword_bonus_capped_at_15(self):
        lead = lg.make_lead(
            "Local Business",
            description="small business local appointment scheduling",
        )
        config = _sample_config(
            target_keywords=["small business", "local", "appointment", "scheduling"]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("keyword_matches", 0) <= 15

    def test_exclude_keyword_penalty(self):
        lead = lg.make_lead("Enterprise Corp", description="enterprise fortune 500")
        config = _sample_config(exclude_keywords=["enterprise", "fortune 500"])
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("exclude_penalty", 0) < 0

    def test_exclude_penalty_capped_at_40(self):
        lead = lg.make_lead(
            "Big Corp",
            description="enterprise corporate fortune 500",
        )
        config = _sample_config(
            exclude_keywords=["enterprise", "corporate", "fortune 500"]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("exclude_penalty", 0) >= -40

    def test_ideal_size_bonus(self):
        lead = lg.make_lead("Sm Biz", size_indicator="small")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("ideal_size") == 10

    def test_too_large_penalty(self):
        lead = lg.make_lead("Megacorp", size_indicator="enterprise 1000+")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("too_large") == -10

    def test_email_bonus(self):
        lead = lg.make_lead("Biz", email="a@b.com")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("has_email") == 5

    def test_phone_bonus(self):
        lead = lg.make_lead("Biz", phone="555-0100")
        config = _sample_config(
            target_industries=[], target_keywords=[], exclude_keywords=[]
        )
        scored = lg.score_lead(lead, config)
        assert scored["score_breakdown"].get("has_phone") == 3

    def test_score_clamped_0_to_100(self):
        # Max penalty scenario
        lead = lg.make_lead(
            "Enterprise Corp",
            description="enterprise corporate fortune 500",
            size_indicator="enterprise 1000+",
        )
        config = _sample_config(
            target_industries=[],
            target_keywords=[],
            exclude_keywords=["enterprise", "corporate", "fortune 500"],
        )
        scored = lg.score_lead(lead, config)
        assert 0 <= scored["score"] <= 100


# ---------------------------------------------------------------------------
# Discernment filter
# ---------------------------------------------------------------------------

class TestDiscernment:
    def test_deduplication(self):
        lead_a = _sample_lead(name="Same Biz", city="Fay", state="AR")
        lead_b = _sample_lead(name="Same Biz", city="Fay", state="AR")
        lead_a["score"] = 70
        lead_b["score"] = 70
        config = _sample_config(min_score_threshold=0)
        result = lg.apply_discernment([lead_a, lead_b], config)
        assert len(result) == 1

    def test_threshold_filter(self):
        low = _sample_lead(name="Low Score")
        low["score"] = 30
        high = _sample_lead(name="High Score")
        high["score"] = 80
        config = _sample_config(min_score_threshold=60)
        result = lg.apply_discernment([low, high], config)
        assert len(result) == 1
        assert result[0]["name"] == "High Score"

    def test_sorted_by_score_descending(self):
        leads = []
        for score in [50, 90, 70, 85]:
            lead = _sample_lead(name=f"Biz{score}", city=str(score))
            lead["score"] = score
            leads.append(lead)
        config = _sample_config(min_score_threshold=0)
        result = lg.apply_discernment(leads, config)
        scores = [l["score"] for l in result]
        assert scores == sorted(scores, reverse=True)

    def test_max_leads_cap(self):
        leads = []
        for i in range(20):
            lead = _sample_lead(name=f"Biz{i}", city=str(i))
            lead["score"] = 70 + i
            leads.append(lead)
        config = _sample_config(min_score_threshold=0, max_leads_per_run=5)
        result = lg.apply_discernment(leads, config)
        assert len(result) == 5

    def test_empty_input(self):
        result = lg.apply_discernment([], _sample_config())
        assert result == []


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_default_config_structure(self):
        cfg = lg.DEFAULT_CONFIG
        assert "target_industries" in cfg
        assert "target_keywords" in cfg
        assert "exclude_keywords" in cfg
        assert "min_score_threshold" in cfg
        assert "max_leads_per_run" in cfg
        assert "geo_targets" in cfg

    def test_load_config_creates_default(self, tmp_path):
        cfg_path = tmp_path / "test_config.json"
        cfg = lg.load_config(cfg_path)
        assert cfg == lg.DEFAULT_CONFIG
        assert cfg_path.exists()

    def test_load_config_reads_existing(self, tmp_path):
        cfg_path = tmp_path / "test_config.json"
        custom = {"target_industries": ["plumbing"], "min_score_threshold": 40}
        with open(cfg_path, "w") as f:
            json.dump(custom, f)
        cfg = lg.load_config(cfg_path)
        assert cfg["target_industries"] == ["plumbing"]
        assert cfg["min_score_threshold"] == 40

    def test_load_config_handles_corrupt_json(self, tmp_path):
        cfg_path = tmp_path / "bad.json"
        cfg_path.write_text("not valid json{{{")
        cfg = lg.load_config(cfg_path)
        assert cfg == lg.DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Scraper graceful degradation
# ---------------------------------------------------------------------------

class TestScrapers:
    def test_google_places_no_key_returns_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PERMANENCE_GOOGLE_PLACES_KEY", None)
            result = lg.scrape_google_places("restaurants", "Fayetteville, AR")
        assert result == []

    def test_yelp_no_key_returns_empty(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PERMANENCE_YELP_API_KEY", None)
            result = lg.scrape_yelp("restaurants", "Fayetteville, AR")
        assert result == []

    def test_yellowpages_no_bs4_returns_empty(self):
        with mock.patch.object(lg, "_HAS_BS4", False):
            result = lg.scrape_yellowpages("restaurants", "Fayetteville, AR")
        assert result == []

    @mock.patch("oca_lead_generator.requests.get")
    def test_google_places_network_error_returns_empty(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("timeout")
        with mock.patch.dict(os.environ, {"PERMANENCE_GOOGLE_PLACES_KEY": "fake_key"}):
            result = lg.scrape_google_places("restaurants", "Fayetteville, AR")
        assert result == []

    @mock.patch("oca_lead_generator.requests.get")
    def test_yelp_network_error_returns_empty(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("timeout")
        with mock.patch.dict(os.environ, {"PERMANENCE_YELP_API_KEY": "fake_key"}):
            result = lg.scrape_yelp("restaurants", "Fayetteville, AR")
        assert result == []

    @mock.patch("oca_lead_generator.requests.get")
    def test_google_places_parses_results(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "name": "Tonys Pizza",
                    "formatted_address": "123 Main St, Fayetteville, AR 72701",
                    "types": ["restaurant", "food"],
                },
            ],
        }
        mock_resp.raise_for_status = mock.MagicMock()
        mock_get.return_value = mock_resp
        with mock.patch.dict(os.environ, {"PERMANENCE_GOOGLE_PLACES_KEY": "fake_key"}):
            result = lg.scrape_google_places("restaurants", "Fayetteville, AR")
        assert len(result) == 1
        assert result[0]["name"] == "Tonys Pizza"
        assert result[0]["source"] == "google_places"

    @mock.patch("oca_lead_generator.requests.get")
    def test_yelp_parses_results(self, mock_get):
        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {
            "businesses": [
                {
                    "name": "Sushi House",
                    "phone": "+15550100",
                    "url": "https://yelp.com/biz/sushi",
                    "location": {
                        "city": "Fayetteville",
                        "state": "AR",
                        "address1": "456 Oak Ave",
                    },
                },
            ],
        }
        mock_resp.raise_for_status = mock.MagicMock()
        mock_get.return_value = mock_resp
        with mock.patch.dict(os.environ, {"PERMANENCE_YELP_API_KEY": "fake_key"}):
            result = lg.scrape_yelp("restaurants", "Fayetteville, AR")
        assert len(result) == 1
        assert result[0]["name"] == "Sushi House"
        assert result[0]["source"] == "yelp"


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

class TestOutput:
    def test_save_outputs_creates_files(self, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            leads = [_sample_lead(name="Test Lead")]
            leads[0]["score"] = 75
            lg._save_outputs(leads, "20260318_120000", leads)
        assert (tmp_path / "leads_20260318_120000.json").exists()
        assert (tmp_path / "leads_20260318_120000.md").exists()

    def test_json_output_structure(self, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            leads = [_sample_lead(name="Test")]
            leads[0]["score"] = 80
            lg._save_outputs(leads, "20260318_120000", leads)
        with open(tmp_path / "leads_20260318_120000.json") as f:
            data = json.load(f)
        assert "leads" in data
        assert "count" in data
        assert data["count"] == 1

    def test_markdown_output_has_table(self, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            leads = [_sample_lead(name="Table Test")]
            leads[0]["score"] = 80
            lg._save_outputs(leads, "20260318_120000", leads)
        content = (tmp_path / "leads_20260318_120000.md").read_text()
        assert "| #" in content
        assert "Table Test" in content


# ---------------------------------------------------------------------------
# Recent leads
# ---------------------------------------------------------------------------

class TestRecentLeads:
    def test_no_output_dir_returns_empty(self, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path / "nonexistent"):
            result = lg.get_recent_leads()
        assert result == []

    def test_loads_most_recent(self, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            # Write two files
            lead_old = _sample_lead(name="Old")
            lead_old["score"] = 70
            with open(tmp_path / "leads_20260101_000000.json", "w") as f:
                json.dump({"leads": [lead_old]}, f)
            lead_new = _sample_lead(name="New")
            lead_new["score"] = 90
            with open(tmp_path / "leads_20260318_120000.json", "w") as f:
                json.dump({"leads": [lead_new]}, f)
            result = lg.get_recent_leads()
        assert len(result) == 1
        assert result[0]["name"] == "New"


# ---------------------------------------------------------------------------
# run_scan integration (mocked network)
# ---------------------------------------------------------------------------

class TestRunScan:
    @mock.patch("oca_lead_generator.scrape_yellowpages", return_value=[])
    @mock.patch("oca_lead_generator.scrape_yelp", return_value=[])
    @mock.patch("oca_lead_generator.scrape_google_places", return_value=[])
    def test_scan_no_results(self, mock_gp, mock_yelp, mock_yp, tmp_path):
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            result = lg.run_scan(
                industry="restaurants",
                geo="Fayetteville, AR",
                config=_sample_config(),
            )
        assert result["count"] == 0
        assert result["total_scraped"] == 0

    @mock.patch("oca_lead_generator.scrape_yellowpages", return_value=[])
    @mock.patch("oca_lead_generator.scrape_yelp", return_value=[])
    @mock.patch("oca_lead_generator.scrape_google_places")
    def test_scan_with_results(self, mock_gp, mock_yelp, mock_yp, tmp_path):
        mock_gp.return_value = [
            lg.make_lead("Good Lead", industry="restaurants", email="a@b.com", size_indicator="small"),
        ]
        with mock.patch.object(lg, "OUTPUT_DIR", tmp_path):
            result = lg.run_scan(
                industry="restaurants",
                geo="Fayetteville, AR",
                config=_sample_config(min_score_threshold=0),
            )
        assert result["count"] >= 1
        assert result["total_scraped"] == 1
        assert result["leads"][0]["score"] > 0
