"""
统一的 LLM 客户端
后面所有脚本都从这里 import，避免重复初始化代码
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
# client = OpenAI(
#     api_key=os.getenv("MOONSHOT_API_KEY"),
#     base_url=os.getenv("MOONSHOT_BASE_KEY"),
# )

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

# DEFAULT_MODEL = "kimi-k2.6"

DEFAULT_MODEL = "gpt-4o-mini"