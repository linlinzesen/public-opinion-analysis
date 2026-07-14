"""最小化 OpenAI 兼容客户端，只依赖 Python 标准库。"""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import get_config


class LLMServiceError(RuntimeError):
    """可安全返回给业务层的大模型调用异常。"""


def chat_completion(
    messages: list[dict[str, str]], temperature: float = 0.2
) -> dict[str, Any]:
    config = get_config()
    if config.mock_mode:
        raise LLMServiceError("当前为 mock 模式，未调用真实大模型")
    if not config.api_key:
        raise LLMServiceError("未配置 LLM_API_KEY")

    payload = json.dumps(
        {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        f"{config.base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        if not content:
            raise LLMServiceError("大模型返回了空内容")
        return {"content": content, "model": config.model}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LLMServiceError(f"大模型 API 返回 HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise LLMServiceError(f"大模型 API 连接失败: {exc}") from exc
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMServiceError("大模型 API 返回格式异常") from exc
