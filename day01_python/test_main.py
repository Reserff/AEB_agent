from math import isinf

from day01_python.main import (
    analyze_case,
    calculate_ttc,
    classify_risk,
    detect_abnormal,
)


def test_risk_thresholds() -> None:
    assert classify_risk(1.49) == "HIGH"
    assert classify_risk(1.5) == "MEDIUM"
    assert classify_risk(2.99) == "MEDIUM"
    assert classify_risk(3.0) == "LOW"


def test_non_positive_relative_speed_has_no_finite_ttc() -> None:
    assert isinf(calculate_ttc(10.0, 0.0))
    assert isinf(calculate_ttc(10.0, -2.0))


def test_high_risk_without_braking_is_abnormal() -> None:
    assert detect_abnormal("HIGH", False) == "ABNORMAL"
    assert detect_abnormal("HIGH", True) == "NORMAL"


def test_analyze_case() -> None:
    result = analyze_case(
        {
            "case_id": "AEB_TEST",
            "speed_mps": 15.0,
            "distance_m": 8.0,
            "relative_speed_mps": 10.0,
            "brake_triggered": False,
        }
    )

    assert result == {
        "case_id": "AEB_TEST",
        "ttc": 0.8,
        "risk": "HIGH",
        "status": "ABNORMAL",
    }
