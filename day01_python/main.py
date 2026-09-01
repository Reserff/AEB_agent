from pathlib import Path
import json


def main():
    p = Path(__file__).parent / "cases.json"
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        print("Loaded cases:", data)
    else:
        print("cases.json not found")


if __name__ == "__main__":
    main()
