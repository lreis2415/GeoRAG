"""
模型管理服务
负责管理嵌入模型和聊天模型
"""

import logging
from typing import List

import yaml

from .base_service import BaseService


class ModelService(BaseService):
    """模型管理服务类"""

    def __init__(self):
        super().__init__()
        self.default_embed_model = "text-embedding-v4"
        self.default_chat_model = "qwen-turbo-latest"

    def get_available_embedding_models(self) -> List[str]:
        """
        获取当前系统中可用的嵌入模型列表

        Returns:
            包含模型名称的列表
        """
        try:
            with open("models.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            models = [model["name"] for model in config.get("embedding_models", [])]
            self.log_info(f"成功加载 {len(models)} 个嵌入模型")
            return models
        except Exception as e:
            self.log_error(f"加载嵌入模型失败: {e}")
            return []

    def get_available_chat_models(self) -> List[str]:
        """
        获取当前系统中可用的聊天模型列表

        Returns:
            包含模型名称的列表
        """
        try:
            with open("models.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            models = [model["name"] for model in config.get("chat_models", [])]
            self.log_info(f"成功加载 {len(models)} 个聊天模型")
            return models
        except Exception as e:
            self.log_error(f"加载聊天模型失败: {e}")
            return []

    def validate_embedding_model(self, model_name: str) -> bool:
        """
        验证嵌入模型是否可用

        Args:
            model_name: 模型名称

        Returns:
            模型是否可用
        """
        available_models = self.get_available_embedding_models()
        return model_name in available_models

    def validate_chat_model(self, model_name: str) -> bool:
        """
        验证聊天模型是否可用

        Args:
            model_name: 模型名称

        Returns:
            模型是否可用
        """
        available_models = self.get_available_chat_models()
        return model_name in available_models

    def get_default_embedding_model(self) -> str:
        """获取默认嵌入模型"""
        return self.default_embed_model

    def get_default_chat_model(self) -> str:
        """获取默认聊天模型"""
        return self.default_chat_model
