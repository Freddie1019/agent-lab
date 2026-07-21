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
        {"role": "user", "content": "请仔细介绍一下西方经济学是什么"}
    ],
    # stream=True
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

# ✅ 修改1：遍历迭代器，逐块接收
# print("=== 流式回答 ===")
# collected_content = []  # 用于拼接完整内容（可选）

# for chunk in response:
#     # 每个chunk的结构：Chunk(id=..., choices=[Delta(..., content='...')])
#     delta = chunk.choices[0].delta
#     if delta.content:
#         print(delta.content, end="", flush=True)  # 实时打印，不换行
#         collected_content.append(delta.content)

# 打印完成后换行
# print("\n\n=== 完整拼接结果 ===")
# print("".join(collected_content))


