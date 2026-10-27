import json

import pytest

from day01_python.main import analyze_case
from day07_batch.loader import parse_cases


def test_parse_csv_and_analyze():

    content = (
        b"case_id,distance_m,"
        b"relative_speed_mps,brake_triggered\n"
        b"AEB_001,8,10,false\n"
    )

    cases = parse_cases("cases.csv", content)

    assert len(cases) == 1

    result = analyze_case(
        cases[0].model_dump()
    )

    assert result["ttc"] == 0.8
    assert result["risk"] == "HIGH"
    assert result["abnormal"] is True


def test_parse_json():

    data = [
        {
            "case_id": "AEB_002",
            "distance_m": 20,
            "relative_speed_mps": 0,
            "brake_triggered": False,
        }
    ]

    content = json.dumps(data).encode("utf-8")

    cases = parse_cases("cases.json", content)

    assert len(cases) == 1
    assert cases[0].case_id == "AEB_002"


def test_invalid_brake_status():

    content = (
        b"case_id,distance_m,"
        b"relative_speed_mps,brake_triggered\n"
        b"AEB_003,8,10,unknown\n"
    )

    with pytest.raises(ValueError):
        parse_cases("cases.csv", content)


def test_unsupported_file_type():

    with pytest.raises(ValueError):
        parse_cases("cases.txt", b"hello")