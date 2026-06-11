"""
Token 计算工具
注意：OpenAI 的 messages 数组 token 数有特殊计算规则
参考：https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
"""
import tiktoken

def get_encoder(model: str = "gpt-4o-mini"):
    """获取对应模型的 tokenizer """
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # 未知模型，用通用 encoder
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """计算单段文本的 token 数"""
    enc = get_encoder(model)
    return len(enc.encode(text))

def count_messages_tokens(messages: list, model: str = "gpt-4o-mini") -> int:
    """
    计算 messages 数组的总 token 数
    每条消息有固定开销（role标识、分隔符等）
    """
    enc = get_encoder(model)
    # 每条消息的固定开销（OpenAI 文档给出的经验值）
    tokens_per_message = 4
    tokens_per_name = 1

    total = 0
    for message in messages:
        total += tokens_per_message
        # 处理 dict 或对象两种形式
        msg_dict = message if isinstance(message, dict) else message.model_dump()

        for key, value in msg_dict.items():
            if value is None:
                continue
            if isinstance(value, str):
                total += len(enc.encode(value))
            elif isinstance(value, list):
                # tool_calls 等结构
                import json
                total += len(enc.encode(json.dumps(value, ensure_ascii=False)))
            if key == "name":
                total += tokens_per_name
    
    total += 3
    return total
