import os


REQUIRED_SETTINGS = (
    "GLM_MODEL",
    "GLM_API_KEY",
)


def get_missing_settings() -> list[str]:
    """检查必需的环境变量是否存在。"""

    return [
        name
        for name in REQUIRED_SETTINGS
        if not os.getenv(name)
    ]