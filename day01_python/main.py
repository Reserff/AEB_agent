"""A small analyzer for Autonomous Emergency Braking (AEB) cases."""

import json
from pathlib import Path
from typing import TypedDict


class AEBCase(TypedDict):
    """Input fields required for one AEB case."""

    case_id: str
    speed_mps: float
    distance_m: float
    relative_speed_mps: float
    brake_triggered: bool


class AnalysisResult(TypedDict):
    """Calculated values displayed for one AEB case."""

    case_id: str
    ttc: float
    risk: str
    status: str


def load_cases(file_path: str | Path) -> list[AEBCase]:
    """Load AEB cases from a UTF-8 JSON file."""

    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("cases.json must contain a JSON array")

    return cases


def calculate_ttc(distance: float, relative_speed: float) -> float:
    """Calculate time to collision in seconds.

    A non-positive relative speed means the objects are not getting closer, so
    there is no finite collision time.
    """

    if relative_speed <= 0:
        return float("inf")
    return distance / relative_speed


def classify_risk(ttc: float) -> str:
    """Classify collision risk using the specified TTC thresholds."""

    if ttc < 1.5:
        return "HIGH"
    if ttc < 3:
        return "MEDIUM"
    return "LOW"


def detect_abnormal(risk: str, brake_triggered: bool) -> str:
    """Flag a high-risk case with no brake activation as abnormal."""

    if risk == "HIGH" and not brake_triggered:
        return "ABNORMAL"
    return "NORMAL"


def analyze_case(case: AEBCase) -> AnalysisResult:
    """Calculate all output fields for one AEB case."""

    ttc = calculate_ttc(case["distance_m"], case["relative_speed_mps"])
    risk = classify_risk(ttc)
    status = detect_abnormal(risk, case["brake_triggered"])

    return {
        "case_id": case["case_id"],
        "ttc": ttc,
        "risk": risk,
        "status": status,
    }


def print_result(result: AnalysisResult) -> None:
    """Print one analysis result in the required human-readable format."""

    print(f'Case: {result["case_id"]}')
    print(f'TTC: {result["ttc"]:.2f} s')
    print(f'Risk: {result["risk"]}')
    print(f'Status: {result["status"]}')


def main() -> None:
    """Load, analyze, and print every case in cases.json."""

    cases_path = Path(__file__).with_name("cases.json")
    cases = load_cases(cases_path)

    for index, case in enumerate(cases):
        if index > 0:
            print()
        print_result(analyze_case(case))


if __name__ == "__main__":
    main()
