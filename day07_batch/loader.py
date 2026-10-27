import csv
import io
import json

from pathlib import Path

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
)


class AEBCaseRecord(BaseModel):
    """单条 AEB 数据的输入结构。"""

    case_id: str = Field(min_length=1)

    distance_m: float = Field(
        ge=0,
        allow_inf_nan=False,
    )

    relative_speed_mps: float = Field(
        allow_inf_nan=False,
    )

    brake_triggered: bool


def parse_cases(
    filename: str,
    content: bytes,
) -> list[AEBCaseRecord]:
    """将 CSV 或 JSON 文件转换为 AEB 数据列表。"""

    suffix = Path(filename).suffix.lower()

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            "文件必须使用 UTF-8 编码"
        ) from exc

    if suffix == ".json":
        try:
            rows = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "JSON 文件格式不正确"
            ) from exc

    elif suffix == ".csv":
        reader = csv.DictReader(
            io.StringIO(text)
        )
        rows = list(reader)

    else:
        raise ValueError(
            "仅支持 .csv 和 .json 文件"
        )

    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "文件必须包含至少一条 AEB 数据"
        )

    cases = []

    for index, row in enumerate(rows, start=1):
        try:
            case = AEBCaseRecord.model_validate(row)
        except ValidationError as exc:
            raise ValueError(
                f"第 {index} 条 AEB 数据不合法：{exc}"
            ) from exc

        cases.append(case)

    return cases