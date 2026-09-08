from day02_tool_calling.agent import analyze_aeb_case


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
