"""
模型管理服务
负责管理嵌入模型和聊天模型

默认从 OpenAI 兼容网关（如 new-api）的 /v1/models 动态拉取可用模型列表，
拉取失败或分类异常时回退到静态 models.yaml。可通过 MODEL_SOURCE=yaml 强制走静态配置。
"""

import os
import threading
import time
from typing import List, Optional, Tuple

import httpx
import yaml

from .base_service import BaseService

MODEL_CACHE_TTL_SECONDS = 300
MODEL_FETCH_TIMEOUT_SECONDS = 3.0


class ModelService(BaseService):
    """模型管理服务类"""

    def __init__(self):
        super().__init__()
        self.default_embed_model = os.environ.get(
            "DEFAULT_EMBEDDING_MODEL", "text-embedding-v4"
        )
        self.default_chat_model = os.environ.get("DEFAULT_CHAT_MODEL", "qwen3.7-plus")
        self._cache_lock = threading.Lock()
        self._cached_models: Optional[List[str]] = None
        self._cached_at = 0.0
        self._last_fallback_log_at = 0.0

    def get_available_embedding_models(self, refresh: bool = False) -> List[str]:
        """
        获取当前系统中可用的嵌入模型列表

        Args:
            refresh: 跳过缓存强制从网关重新拉取

        Returns:
            包含模型名称的列表
        """
        _, _, embedding_models = self._resolve_available_models(refresh=refresh)
        return embedding_models

    def get_available_chat_models(self, refresh: bool = False) -> List[str]:
        """
        获取当前系统中可用的聊天模型列表

        Args:
            refresh: 跳过缓存强制从网关重新拉取

        Returns:
            包含模型名称的列表
        """
        _, chat_models, _ = self._resolve_available_models(refresh=refresh)
        return chat_models

    def get_model_source(self, refresh: bool = False) -> str:
        """获取当前模型列表的来源（gateway 或 yaml）"""
        source, _, _ = self._resolve_available_models(refresh=refresh)
        return source

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

    def _resolve_available_models(
        self, refresh: bool = False
    ) -> Tuple[str, List[str], List[str]]:
        """返回 (来源, 聊天模型列表, 嵌入模型列表)，网关不可用时整体回退 models.yaml"""
        gateway_models = self._get_gateway_models(force=refresh)
        if gateway_models is not None:
            embedding = [m for m in gateway_models if "embedding" in m.lower()]
            chat = [m for m in gateway_models if "embedding" not in m.lower()]
            if embedding and chat:
                return "gateway", chat, embedding
            self._log_fallback(
                f"网关模型分类异常（chat={len(chat)}, embedding={len(embedding)}），"
                "回退 models.yaml"
            )
        yaml_chat = self._load_yaml_models("chat_models", "聊天")
        yaml_embedding = self._load_yaml_models("embedding_models", "嵌入")
        return "yaml", yaml_chat, yaml_embedding

    def _get_gateway_models(self, force: bool = False) -> Optional[List[str]]:
        """带 TTL 缓存的网关模型列表；未启用或失败时返回 None"""
        if os.environ.get("MODEL_SOURCE", "gateway").lower() == "yaml":
            return None
        with self._cache_lock:
            if (
                not force
                and self._cached_models is not None
                and time.monotonic() - self._cached_at < MODEL_CACHE_TTL_SECONDS
            ):
                return self._cached_models
        models = self._fetch_gateway_models()
        if models is not None:
            with self._cache_lock:
                self._cached_models = models
                self._cached_at = time.monotonic()
        return models

    def _fetch_gateway_models(self) -> Optional[List[str]]:
        """从网关 GET {OPENAI_API_BASE}/models 拉取模型 id 列表；失败返回 None"""
        api_base = os.environ.get("OPENAI_API_BASE")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_base or not api_key:
            self._log_fallback(
                "未配置 OPENAI_API_BASE/OPENAI_API_KEY，回退 models.yaml"
            )
            return None
        try:
            response = httpx.get(
                f"{api_base.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=MODEL_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            models = [item["id"] for item in payload.get("data", []) if item.get("id")]
            self.log_info(f"成功从网关拉取 {len(models)} 个模型")
            return models
        except Exception as e:
            self._log_fallback(f"从网关拉取模型列表失败: {e}，回退 models.yaml")
            return None

    def _log_fallback(self, reason: str) -> None:
        # 稳态下每个 TTL 周期最多记录一次，避免高频请求刷屏
        now = time.monotonic()
        if now - self._last_fallback_log_at >= MODEL_CACHE_TTL_SECONDS:
            self._last_fallback_log_at = now
            self.log_warning(reason)

    def _load_yaml_models(self, section: str, label: str) -> List[str]:
        """从静态 models.yaml 读取模型名称列表（兜底数据源）"""
        try:
            with open("models.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            models = [
                model["name"]
                for model in config.get(section, [])
                if isinstance(model, dict) and model.get("name")
            ]
            self.log_info(f"从 models.yaml 加载 {len(models)} 个{label}模型")
            return models
        except Exception as e:
            self.log_error(f"加载{label}模型失败: {e}")
            return []
