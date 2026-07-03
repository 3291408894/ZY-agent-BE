"""LLM 客户端封装 — OpenAI 兼容接口，支持流式和非流式调用"""

import json
from typing import AsyncIterator
import httpx
from loguru import logger

from app.core.config import settings


class LLMClient:
    """LLM API 客户端（OpenAI 兼容协议）"""

    def __init__(self) -> None:
        self.api_base = settings.LLM_API_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.max_retries = 3
        self.timeout = 120.0  # 流式请求需要较长超时

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """非流式调用，返回完整回复文本"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.post(
                        f"{self.api_base}/chat/completions",
                        headers=self._headers,
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"LLM 非流式调用成功 | model={self.model} | tokens={data.get('usage', {}).get('total_tokens', '?')}")
                    return content
                except Exception as e:
                    logger.warning(f"LLM 调用失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt == self.max_retries - 1:
                        raise

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """流式调用，逐块返回增量文本"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    async with client.stream(
                        "POST",
                        f"{self.api_base}/chat/completions",
                        headers=self._headers,
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "stream": True,
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    return
                                try:
                                    data = json.loads(data_str)
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                                except json.JSONDecodeError:
                                    continue
                    return  # 正常完成
                except Exception as e:
                    logger.warning(f"LLM 流式调用失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                    if attempt == self.max_retries - 1:
                        raise


# 全局单例
llm_client = LLMClient()
