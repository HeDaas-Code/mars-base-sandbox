"""
配置模块 - 赫拉克勒斯协议原型
管理 API 密钥、模型选择、ChromaDB 路径等全局配置
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """全局配置"""

    # LLM API 配置（OpenAI 兼容接口）
    # Dr.Dream 03:24 提供测试 API：MiniMax-M3，OpenAI 兼容
    # 环境变量优先：LLM_API_KEY / LLM_BASE_URL
    # 回退到 OPENAI_API_KEY（兼容旧配置）
    llm_api_key: str = field(
        default_factory=lambda: os.getenv(
            "LLM_API_KEY", os.getenv("OPENAI_API_KEY", "")
        )
    )
    llm_base_url: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", "http://117.72.106.189:3000/v1"
        )
    )

    # 模型配置（MiniMax-M3，OpenAI 兼容接口调用）
    model_deliberate: str = "MiniMax-M3"  # 审慎式：平衡速度与质量
    model_deep: str = "MiniMax-M3"        # 深思式：高质量

    # ChromaDB 配置
    chroma_persist_dir: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "chroma_db",
        )
    )
    chroma_collection_name: str = "heracles_memories"

    # LangGraph checkpoint
    checkpoint_db_path: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "checkpoints.sqlite",
        )
    )

    # 记忆检索
    memory_top_k: int = 3
    max_history_messages: int = 6  # 对话历史窗口（云逸 P2 #7）

    # 滑动窗口 K 值（接口规范 §7.3.2）
    # reflexive 不压缩；deliberate K=6；deep K=10
    history_window_k: dict = field(
        default_factory=lambda: {"reflexive": 0, "deliberate": 6, "deep": 10}
    )
    # 压缩触发阈值（messages 数超过此值才压缩）
    compress_threshold: dict = field(
        default_factory=lambda: {"reflexive": 0, "deliberate": 10, "deep": 16}
    )

    # Agent 配置
    agent_id: str = "chen_hao"  # 陈昊

    def validate(self) -> bool:
        """检查必要配置是否就绪"""
        if not self.llm_api_key:
            print("[WARN] LLM_API_KEY 未设置，LLM 调用将使用 Mock 模式")
            return False
        return True


# 全局配置实例
config = Config()
