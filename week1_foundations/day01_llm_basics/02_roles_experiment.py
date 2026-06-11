import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载 .env 里的环境变量
load_dotenv()
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def ask(messages):
    """封装调用"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content

# === 实验 1：没有 system 提示词 ===
print("=== 实验 1：无 system ===")
print(ask([
    {"role": "user", "content": "你是谁？"}
]))

# === 实验 2：用 system 设定人设 ===
print("\n=== 实验 2：海盗人设 ===")
print(ask([
    {"role": "system", "content": "你是一个 17 世纪的海盗，说话要带海盗口吻，每句话都要带'啊哈'"},
    {"role": "user", "content": "你是谁？"}
]))

# === 实验 3：手动构造多轮对话历史 ===
print("\n=== 实验 3：多轮上下文 ===")
print(ask([
    {"role": "system", "content": "你是一个数学老师"},
    {"role": "user", "content": "什么是质数？"},
    {"role": "assistant", "content": "质数是只能被 1 和自己整除的大于 1 的自然数。"},
    {"role": "user", "content": "举三个例子"}  # ← 注意：这里能不能"举三个例子"成功，依赖于前面的上下文
]))

# === 实验 4：故意把 user 和 assistant 颠倒 ===
print("\n=== 实验 4：颠倒角色（看会发生什么）===")
print(ask([
    {"role": "user", "content": "我喜欢吃苹果"},
    {"role": "assistant", "content": "我喜欢吃香蕉"},   # 假装 LLM 之前说过这话
    {"role": "user", "content": "我们俩谁喜欢吃苹果？"}
]))