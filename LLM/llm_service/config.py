"""配置项：全部从环境变量读取，避免把密钥提交到代码仓库。"""

import os
from dataclasses import dataclass


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout: int
    mock_mode: bool


def get_config() -> LLMConfig:
    """每次调用时重新读取环境变量，便于测试和部署时动态配置。"""
    api_key = os.getenv("LLM_API_KEY", "sk-2b4c81db82374941afe9972e7f1cf9c0")
    return LLMConfig(
        api_key=api_key,
        base_url=os.getenv(
            "LLM_BASE_URL", "https://api.deepseek.com/v1"
        ).rstrip("/"),
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        timeout=int(os.getenv("LLM_TIMEOUT", "30")),
        # 未设置 Key 时默认 mock；也可显式设置 LLM_MOCK=true。
        mock_mode=_as_bool(
            os.getenv("LLM_MOCK", "true" if not api_key else "false")
        ),
    )
