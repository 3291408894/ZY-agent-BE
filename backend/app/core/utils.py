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
    """从 LLM 回复中提取 JSON 字符串"""
    # 尝试匹配 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    # 尝试直接匹配 JSON 对象
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    # 尝试直接匹配 JSON 数组
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        return match.group(0)
    return None
