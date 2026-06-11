from importlib.resources import contents
import os
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.beta import assistant

# 加载 .env 里的环境变量
load_dotenv()
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

# 初始化对话历史
messages = [
    {"role":"system", "content": "你是一个简介、友好的助手，回答控制在100字以内。"}
]

print("命令行助手已启动（输入 'quit' 退出，'clear' 清空历史，'history' 查看历史）\n")

while True:
    # 1.接收用户输入
    user_input = input("你：").strip()

    if not user_input:
        continue

    if user_input == "quit":
        print("再见")
        break

    if user_input == "claer":
        messages = messages[:1] # 保留 system 提示
        print("历史已清空")
        continue
    
    if user_input == "history":
        for msg in messages:
            print(f"  [{msg['role']}] {msg['content'][:50]}...")
        print()
        continue

    # 2. 把用户消息加入历史
    messages.append({"role": "user", "content": user_input})

    # 3. 调用LLM
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
    )

    # 4. 提取回答
    assistant_reply = response.choices[0].message.content

    # 5. 关键步骤：把 LLM 的回答也加入历史
    messages.append({"role": "assistant", "content": assistant_reply})

    # 6. 打印
    print(f"AI: {assistant_reply}")
    print(f"   (本轮 token: {response.usage.total_tokens}, 累计消息数: {len(messages)})\n")