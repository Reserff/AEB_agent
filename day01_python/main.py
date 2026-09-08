"""A small analyzer for Autonomous Emergency Braking (AEB) cases."""

import json
from pathlib import Path
from typing import TypedDict


class AEBAnalysisInput(TypedDict):
    """Fields used to analyze one AEB case."""

    case_id: str
    distance_m: float
    relative_speed_mps: float
    brake_triggered: bool


class AEBCase(AEBAnalysisInput):
    """Complete AEB case loaded from the input data file."""

    speed_mps: float


class AnalysisResult(TypedDict):
    """Structured result returned by the AEB analysis tool."""

    case_id: str
    ttc: float
    risk: str
    abnormal: bool

# 加载cases数据文件
def load_cases(file_path: str | Path) -> list[AEBCase]:
    """Load AEB cases from a UTF-8 JSON file."""

    path = Path(file_path)
    with path.open("r", encoding="utf-8") as file:
        # 读取cases.json文件
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("cases.json must contain a JSON array")

    return cases

# 计算TTC
def calculate_ttc(distance: float, relative_speed: float) -> float:
    """Calculate time to collision in seconds.

    A non-positive relative speed means the objects are not getting closer, so
    there is no finite collision time.
    """

    if relative_speed <= 0:
        return float("inf")
    return distance / relative_speed

# 危险等级分类
def classify_risk(ttc: float) -> str:
    """Classify collision risk using the specified TTC thresholds."""

    if ttc < 1.5:
        return "HIGH"
    if ttc < 3:
        return "MEDIUM"
    return "LOW"

# 检测异常
def detect_abnormal(risk: str, brake_triggered: bool) -> bool:
    """Flag a high-risk case with no brake activation as abnormal."""

    return risk == "HIGH" and not brake_triggered

# 分析数据
def analyze_case(case: AEBAnalysisInput) -> AnalysisResult:
    """Calculate all output fields for one AEB case."""

    ttc = calculate_ttc(case["distance_m"], case["relative_speed_mps"])
    risk = classify_risk(ttc)
    abnormal = detect_abnormal(risk, case["brake_triggered"])

    return {
        "case_id": case["case_id"],
        "ttc": ttc,
        "risk": risk,
        "abnormal": abnormal,
    }


# 打印结果
def display_result(result: AnalysisResult) -> None:
    """Display a structured analysis result in a human-readable format."""

    status = "ABNORMAL" if result["abnormal"] else "NORMAL"
    print(f'Case: {result["case_id"]}')
    print(f'TTC: {result["ttc"]:.2f} s')
    print(f'Risk: {result["risk"]}')
    print(f"Status: {status}")

# 主函数，循环执行
def main() -> None:
    """Load, analyze, and print every case in cases.json."""

    cases_path = Path(__file__).with_name("cases.json")
    cases = load_cases(cases_path)

    for index, case in enumerate(cases):
        if index > 0:
            print()
        result = analyze_case(case)
        display_result(result)


if __name__ == "__main__":
    main()
