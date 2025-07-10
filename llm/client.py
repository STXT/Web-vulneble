from openai import OpenAI

# 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
def get_client(api_key='sk-1cb7a52f34da4e44a4974be96e33c591' # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
               , base_url="https://api.deepseek.com"): 
    return OpenAI(api_key=api_key, base_url=base_url)


def get_ai_response(client, prompt, history=None, model="deepseek-chat", max_tokens=1000):
    """
    调用LLM获取响应
    """
    if history is None:
        history = []
    
    messages = [{"role": "user", "content": prompt}]
    print(messages)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling AI model: {e}")
        return ""