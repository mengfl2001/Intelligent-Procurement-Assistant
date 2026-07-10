import asyncio
import aiohttp

async def test_api():
    api_key = input("请输入您的 API Key: ").strip()
    base_url = input("请输入您的 Base URL: ").strip()
    model_name = input("请输入模型名称 (如 qwen3.6-flash): ").strip()
    
    print(f"\n测试配置:")
    print(f"API Key: {api_key[:10]}...")
    print(f"Base URL: {base_url}")
    print(f"模型: {model_name}")
    print("-" * 50)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    test_payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 10
    }
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            test_url = f"{base_url.rstrip('/')}/chat/completions"
            print(f"请求 URL: {test_url}")
            
            async with session.post(test_url, headers=headers, json=test_payload) as response:
                status = response.status
                error_text = await response.text()
                print(f"\n响应状态码: {status}")
                print(f"响应内容: {error_text[:500]}")
                
    except Exception as e:
        print(f"请求异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_api())