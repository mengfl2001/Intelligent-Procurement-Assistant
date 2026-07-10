import asyncio
from typing import Dict, Any

import aiohttp


class APIClient:
    def __init__(self):
        self._api_key: str = ""
        self._base_url: str = ""
        self._model_name: str = ""

    def set_config(self, api_key: str, base_url: str, model_name: str):
        self._api_key = api_key.strip()
        self._base_url = base_url.strip().rstrip("/")
        self._model_name = model_name.strip()

    async def test_connection(self) -> Dict[str, Any]:
        if not self._api_key or not self._base_url:
            return {"success": False, "message": "API Key 和 Base URL 不能为空"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        test_url = f"{self._base_url}/chat/completions"
        model_to_use = self._model_name if self._model_name else "qwen-plus"

        test_payload = {
            "model": model_to_use,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(test_url, headers=headers, json=test_payload) as response:
                    status = response.status
                    error_text = await response.text()
                    if status == 200:
                        return {"success": True, "message": "API 连接测试成功"}
                    elif status == 404:
                        return {"success": False, "message": f"404 路径不存在！请检查 Base URL 是否正确。\n请求路径: {test_url}\n模型: {model_to_use}"}
                    elif status == 401:
                        return {"success": False, "message": f"401 鉴权失败！请检查 API Key 是否正确。"}
                    elif status == 429:
                        return {"success": False, "message": f"429 请求过于频繁，请稍后重试。"}
                    else:
                        return {"success": False, "message": f"连接失败，状态码: {status}\n错误信息: {error_text[:300]}"}
        except asyncio.TimeoutError:
            return {"success": False, "message": "连接超时，请检查网络或 Base URL"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}\n请求路径: {test_url}"}

    async def process_purchase_task(self, data: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        prompt = self._build_purchase_prompt(data)
        model_to_use = self._model_name if self._model_name else "qwen-plus"

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": "你是一个智能采购助手，请根据用户提供的采购需求信息，分析并生成采购建议。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return {"success": True, "data": {"response": content}}
                    else:
                        error_text = await response.text()
                        return {"success": False, "message": f"请求失败，状态码: {response.status}，错误: {error_text[:300]}"}
        except Exception as e:
            return {"success": False, "message": f"请求失败: {str(e)}"}

    def _build_purchase_prompt(self, data: Dict[str, Any]) -> str:
        lines = ["请根据以下采购需求信息进行分析："]
        for key, value in data.items():
            lines.append(f"- {key}: {value}")
        lines.append("\n请提供详细的采购建议，包括：")
        lines.append("1. 产品规格分析")
        lines.append("2. 推荐供应商")
        lines.append("3. 价格预估")
        lines.append("4. 采购注意事项")
        return "\n".join(lines)

    async def chat_completion(self, messages: list) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        model_to_use = self._model_name if self._model_name else "qwen-plus"

        payload = {
            "model": model_to_use,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        return {"success": True, "content": content}
                    else:
                        error_text = await response.text()
                        return {"success": False, "message": f"请求失败，状态码: {response.status}，错误: {error_text[:300]}"}
        except Exception as e:
            return {"success": False, "message": f"请求失败: {str(e)}"}


api_client = APIClient()