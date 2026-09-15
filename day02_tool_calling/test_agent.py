from day02_tool_calling.agent import analyze_aeb_case, tools
import pytest


def test_analyze_aeb_case_high_risk() -> None:
    result = analyze_aeb_case(
        distance_m=8.0,
        relative_speed_mps=10.0,
        brake_triggered=False,
    )

    assert result == {
        "ttc": 0.8,
        "risk": "HIGH",
        "abnormal": True,
    }


def test_analyze_aeb_case_low_risk() -> None:
    result = analyze_aeb_case(
        distance_m=50.0,
        relative_speed_mps=5.0,
        brake_triggered=False,
    )

    assert result == {
        "ttc": 10.0,
        "risk": "LOW",
        "abnormal": False,
    }


def test_analyze_aeb_case_tool_schema() -> None:
    assert len(tools) == 1

    tool = tools[0]

    assert tool["type"] == "function"

    function = tool["function"]

    assert function["name"] == "analyze_aeb_case"

    parameters = function["parameters"]

    assert parameters["type"] == "object"
    assert parameters["additionalProperties"] is False

    assert set(parameters["properties"]) == {
        "distance_m",
        "relative_speed_mps",
        "brake_triggered",
    }

    assert set(parameters["required"]) == set(
        parameters["properties"]
    )

    assert parameters["properties"]["distance_m"]["type"] == "number"
    assert (
        parameters["properties"]["relative_speed_mps"]["type"]
        == "number"
    )
    assert (
        parameters["properties"]["brake_triggered"]["type"]
        == "boolean"
    )
    
def test_negative_distance_is_invalid() -> None:
    with pytest.raises(ValueError):
        analyze_aeb_case(
            distance_m=-10.0,
            relative_speed_mps=5.0,
            brake_triggered=False,
        )