"""
故意设计的"危险工具集"，用来测试 HITL 机制
注意：这些工具操作真实文件系统！测试时只在 /tmp 或临时目录！
"""
import os
import pathlib
from shared.safety import ToolMetadata, DangerLevel
from shared.agent_errors import ToolInvalidArgument


# ===== 限制操作范围（安全护栏）=====
SAFE_WORKING_DIR = pathlib.Path("/tmp/agent_sandbox")
SAFE_WORKING_DIR.mkdir(exist_ok=True)


def _validate_path(path_str: str) -> pathlib.Path:
    """确保 path 在安全沙箱内（防止 ../ 越权）"""
    p = (SAFE_WORKING_DIR / path_str).resolve()
    if not str(p).startswith(str(SAFE_WORKING_DIR.resolve())):
        raise ToolInvalidArgument(f"路径越权: {path_str} 必须在 {SAFE_WORKING_DIR}")
    return p


# ===== 绿色：只读 =====
def list_files(directory: str = ".") -> str:
    p = _validate_path(directory)
    if not p.exists():
        return f"目录不存在: {directory}"
    files = [f.name for f in p.iterdir()]
    return f"目录 {directory} 包含 {len(files)} 个文件: {files}"


def read_file(filename: str) -> str:
    p = _validate_path(filename)
    if not p.is_file():
        return f"文件不存在: {filename}"
    return p.read_text(encoding="utf-8")[:2000]


# ===== 黄色：写但可恢复 =====
def write_file(filename: str, content: str) -> str:
    p = _validate_path(filename)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {filename}（{len(content)} 字符）"


# ===== 红色：不可逆 =====
def delete_file(filename: str) -> str:
    p = _validate_path(filename)
    if not p.is_file():
        return f"文件不存在: {filename}"
    p.unlink()
    return f"已删除 {filename}"


# ===== 工具元数据注册表 =====
DANGEROUS_TOOLS = {
    "list_files": ToolMetadata(
        name="list_files",
        func=list_files,
        danger_level=DangerLevel.GREEN,
        description="列出指定目录的文件",
    ),
    "read_file": ToolMetadata(
        name="read_file",
        func=read_file,
        danger_level=DangerLevel.GREEN,
        description="读取文件内容",
    ),
    "write_file": ToolMetadata(
        name="write_file",
        func=write_file,
        danger_level=DangerLevel.YELLOW,
        description="写入文件（覆盖已存在的）",
    ),
    "delete_file": ToolMetadata(
        name="delete_file",
        func=delete_file,
        danger_level=DangerLevel.RED,
        description="删除文件（不可逆！）",
    ),
}


# ===== LLM Schema =====
DANGEROUS_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出指定目录的文件名",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "default": "."}
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件的文本内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建或覆盖一个文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["filename", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "永久删除一个文件（不可恢复！）",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"}
                },
                "required": ["filename"]
            }
        }
    },
]