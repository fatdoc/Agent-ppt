import json

import pytest

from models.project import Project
from services.ppt_to_ppt.data_models import (
    MatchStrength,
    PagePattern,
    PptToPptBlueprint,
    PptToPptOptions,
)


def test_options_defaults_to_balanced_notes_and_structure_scope():
    options = PptToPptOptions.from_form({})

    assert options.content_type == "notes"
    assert options.match_strength == MatchStrength.BALANCED
    assert options.reference_scope == "structure_and_style"
    assert options.page_count is None


def test_options_rejects_invalid_match_strength():
    try:
        PptToPptOptions.from_form({"match_strength": "pixel_clone"})
    except ValueError as exc:
        assert "match_strength" in str(exc)
    else:
        raise AssertionError("invalid match_strength should raise ValueError")


def test_options_accepts_numeric_page_count():
    options = PptToPptOptions.from_form({"page_count": 12})

    assert options.page_count == 12


def test_options_rejects_non_numeric_page_count():
    with pytest.raises(ValueError, match="page_count"):
        PptToPptOptions.from_form({"page_count": "many"})


def test_options_rejects_out_of_range_page_count():
    with pytest.raises(ValueError, match="page_count"):
        PptToPptOptions.from_form({"page_count": "81"})


def test_options_rejects_invalid_content_type():
    with pytest.raises(ValueError, match="content_type"):
        PptToPptOptions.from_form({"content_type": "spreadsheet"})


def test_options_rejects_invalid_reference_scope():
    with pytest.raises(ValueError, match="reference_scope"):
        PptToPptOptions.from_form({"reference_scope": "pixel_clone"})


def test_blueprint_round_trip_dict():
    blueprint = PptToPptBlueprint(
        deck_summary="Business pitch deck",
        style_profile={"color_palette": "navy and cyan"},
        narrative_profile={"section_flow": ["Opening", "Problem", "Solution"]},
        page_patterns=[
            PagePattern(
                reference_page_index=1,
                page_role="cover",
                layout_pattern="Large title on left",
                content_pattern="Project name and one-line positioning",
                visual_pattern="Abstract hero visual",
            )
        ],
        reference_material_notes=["Use as inspiration, not source content"],
    )

    data = blueprint.to_dict()
    restored = PptToPptBlueprint.from_dict(data)

    assert restored.deck_summary == "Business pitch deck"
    assert restored.page_patterns[0].page_role == "cover"
    assert restored.reference_material_notes == ["Use as inspiration, not source content"]


def test_project_blueprint_helpers_round_trip():
    project = Project(creation_type="ppt_to_ppt")
    payload = {"deck_summary": "Reference deck", "page_patterns": []}

    project.set_ppt_to_ppt_blueprint(payload)

    assert json.loads(project.ppt_to_ppt_blueprint)["deck_summary"] == "Reference deck"
    assert project.get_ppt_to_ppt_blueprint() == payload


def test_project_to_dict_exposes_ppt_to_ppt_blueprint():
    project = Project(creation_type="ppt_to_ppt")
    payload = {"deck_summary": "Reference deck", "page_patterns": []}

    project.set_ppt_to_ppt_blueprint(payload)

    assert project.to_dict()["ppt_to_ppt_blueprint"] == payload
