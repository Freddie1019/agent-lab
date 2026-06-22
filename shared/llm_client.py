"""
统一的 LLM 客户端
后面所有脚本都从这里 import，避免重复初始化代码
"""
# from dotenv import load_dotenv
from openai import OpenAI
from deep_research_agent.core.settings import get_settings

settings = get_settings()
# load_dotenv()
# client = OpenAI(
#     api_key=os.getenv("MOONSHOT_API_KEY"),
#     base_url=os.getenv("MOONSHOT_BASE_KEY"),
# )

client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)

# DEFAULT_MODEL = "kimi-k2.6"

DEFAULT_MODEL = settings.default_model