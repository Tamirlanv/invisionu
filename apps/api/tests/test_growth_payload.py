from pydantic import ValidationError

from invision_api.services.section_payloads import GrowthJourneySectionPayload, growth_journey_section_complete


def _valid_answers() -> dict:
    return {
        "q1": {"text": "x" * 250},
        "q2": {"text": "y" * 200},
        "q3": {"text": "z" * 200},
        "q4": {"text": "a" * 200},
        "q5": {"text": "b" * 150},
    }


def test_growth_payload_valid_boundaries() -> None:
    payload = GrowthJourneySectionPayload.model_validate(
        {
            "answers": _valid_answers(),
            "consent_privacy": True,
            "consent_parent": True,
        }
    )
    assert len(payload.answers["q1"].text) == 250
    assert growth_journey_section_complete(payload) is True


def test_growth_payload_migrates_legacy_narrative() -> None:
    payload = GrowthJourneySectionPayload.model_validate(
        {
            "narrative": "legacy " * 50,
            "consent_privacy": True,
            "consent_parent": True,
        }
    )
    assert "q1" in payload.answers
    assert "legacy" in payload.answers["q1"].text
    assert len(payload.answers["q2"].text) == 200
    assert payload.answers["q2"].text == "." * 200


def test_growth_payload_rejects_short_q1() -> None:
    try:
        GrowthJourneySectionPayload.model_validate(
            {
                "answers": {
                    **{k: v for k, v in _valid_answers().items() if k != "q1"},
                    "q1": {"text": "x" * 100},
                },
                "consent_privacy": True,
                "consent_parent": True,
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected validation error for short q1")


def test_growth_journey_section_complete_requires_consents() -> None:
    payload = GrowthJourneySectionPayload.model_validate(
        {
            "answers": _valid_answers(),
            "consent_privacy": True,
            "consent_parent": True,
        }
    )
    incomplete = payload.model_copy(update={"consent_privacy": False})
    assert growth_journey_section_complete(payload) is True
    assert growth_journey_section_complete(incomplete) is False
