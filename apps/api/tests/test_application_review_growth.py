from invision_api.services.stages.application_review_service import _growth_path_committee_view


def test_growth_path_committee_prefers_section_computed() -> None:
    sections = {
        "growth_journey": {
            "computed": {
                "llm_summary": "Кратко о пути",
                "section_signals": {"k": 1},
                "computed_at": "2026-01-01T00:00:00+00:00",
            }
        }
    }
    out = _growth_path_committee_view(sections, {})
    assert out["llm_summary"] == "Кратко о пути"
    assert out["section_signals"] == {"k": 1}
    assert out["computed_at"] == "2026-01-01T00:00:00+00:00"


def test_growth_path_committee_fallback_to_explainability() -> None:
    sections: dict = {"growth_journey": {}}
    explainability = {
        "by_block": {
            "growth_journey": {
                "explanations": {
                    "llm_summary": "Из запуска",
                    "structured_compact": {"section_signals": {"fallback": True}},
                }
            }
        }
    }
    out = _growth_path_committee_view(sections, explainability)
    assert out["llm_summary"] == "Из запуска"
    assert out["section_signals"] == {"fallback": True}
