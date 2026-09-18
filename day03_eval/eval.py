import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from day02_tool_calling.agent import run_agent

EVAL_FILE = Path(__file__).with_name(
    "eval_cases.json"
)

def load_eval_cases() -> list[dict]:

    with EVAL_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
    
def main() -> None:

    cases = load_eval_cases()

    passed = 0

    for case in cases:

        result = run_agent(
            case["prompt"]
        )

        actual = result["tool_called"]
        expected = case["expected_tool_called"]

        success = actual == expected

        if success:
            passed += 1

        print(
            case["name"],
            "PASS" if success else "FAIL",
        )

    print()
    print(
        f"Score: {passed}/{len(cases)}"
    )
    
if __name__ == "__main__":
    main()
