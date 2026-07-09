"""纯工具函数（无外部依赖，可独立测试）"""

import json
import re


def sse_json(data: dict) -> str:
    """将 dict 序列化为一行 SSE JSON"""
    return json.dumps(data, ensure_ascii=False)


def truncate(text: str, max_len: int) -> str:
    """截断文本，超出部分加省略号"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def extract_json(text: str) -> str | None:
    """从 LLM 回复中提取 JSON 字符串

    使用 raw_decode 精确定位有效 JSON 的结束位置，
    避免 LLM 在 JSON 后追加额外文字导致的 "Extra data" 解析错误。
    """
    # 1. 尝试 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        candidate = match.group(1).strip()
        result = _raw_decode_json(candidate)
        if result is not None:
            return result

    # 2. 从文本中查找 JSON 起始位置并 raw_decode
    stripped = text.strip()
    for start_marker in ["[", "{"]:
        idx = stripped.find(start_marker)
        if idx == -1:
            continue
        result = _raw_decode_json(stripped, idx)
        if result is not None:
            return result

    return None


def _raw_decode_json(text: str, start_idx: int = 0) -> str | None:
    """用 raw_decode 精确截取一段有效 JSON，自动忽略尾部多余文本"""
    decoder = json.JSONDecoder()
    try:
        obj, end = decoder.raw_decode(text, start_idx)
        return text[start_idx : start_idx + end]
    except json.JSONDecodeError:
        return None
