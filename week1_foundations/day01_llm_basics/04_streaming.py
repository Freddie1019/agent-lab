import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url=os.getenv("MOONSHOT_BASE_KEY"),
)


# === 非流式：等完整响应 ===
print("=== 非流式模式 ===")
start = time.time()

response = client.chat.completions.create(
    model="kimi-k2.6",
    messages=[{"role": "user", "content": "用 100 字介绍 Transformer 架构"}],
    stream=False,  # 默认就是 False
)
elapsed = time.time() - start

print(response.choices[0].message.content)
print(f"\n[耗时 {elapsed:.2f}s，期间用户什么都看不到]\n")


# === 流式：边生成边输出 ===
print("=== 流式模式 ===")
start = time.time()
first_token_time = None

stream = client.chat.completions.create(
    model="kimi-k2.6",
    messages=[{"role": "user", "content": "用 100 字介绍 Transformer 架构"}],
    stream=True,  # ← 关键参数
)

full_content = ""
for chunk in stream:
    # 每个 chunk 是一个小片段
    delta = chunk.choices[0].delta.content
    if delta:
        if first_token_time is None:
            first_token_time = time.time() - start
        print(delta, end="", flush=True)  # 立即输出，不缓冲
        full_content += delta

print(f"\n\n[首字延迟 {first_token_time:.2f}s，总耗时 {time.time()-start:.2f}s]")