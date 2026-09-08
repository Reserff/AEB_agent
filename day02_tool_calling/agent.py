import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from day01_python.main import analyze_case

load_dotenv()

client = OpenAI()


def analyze_aeb_case(
    distance_m: float,
    relative_speed_mps: float,
    brake_triggered: bool,
) -> dict:
    """Expose the Day 1 AEB analyzer through an LLM-friendly interface."""

    result = analyze_case(
        {
            "case_id": "AEB_TOOL_INPUT",
            "distance_m": distance_m,
            "relative_speed_mps": relative_speed_mps,
            "brake_triggered": brake_triggered,
        }
    )

    return {
        "ttc": result["ttc"],
        "risk": result["risk"],
        "abnormal": result["abnormal"],
    }
