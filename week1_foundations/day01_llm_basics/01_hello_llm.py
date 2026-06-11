import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 里的环境变量
load_dotenv()

# 创建客户端（自动从环境变量中读key和Base_url）
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

# 第一次调用
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "用一句话介绍ReACT是什么"}
    ],
)

# 打印完整返回
print("=== 完整返回 ===")
print(response)

print("\n=== 提取回答 ===")
print(response.choices[0].message.content)

print("\n=== Token用量 ===")
print(f"输入: {response.usage.prompt_tokens}")
print(f"输出: {response.usage.completion_tokens}")
print(f"总计: {response.usage.total_tokens}")


