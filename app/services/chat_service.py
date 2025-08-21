"""
聊天服务
负责聊天会话管理和对话记忆功能
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from langchain.memory import ConversationBufferMemory
from langchain.schema.messages import BaseMessage
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from .base_service import BaseService

class ChatService(BaseService):
    """聊天服务类"""
    
    def __init__(self):
        super().__init__()
        # 添加会话管理
        self.chat_sessions = {}  # 存储会话记录 {session_id: {"memory": ConversationBufferMemory, "created_at": datetime, "last_active": datetime}}
        self.max_sessions = 100  # 最大会话数
        self.max_memory_length = 20  # 每个会话最大记忆轮次

    
    def create_session(self, session_id: str = None) -> str:
        """
        创建会话
        
        Args:
            session_id: 会话ID，如果为None则创建新会话
            
        Returns:
            会话ID
        """
            
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if session_id not in self.chat_sessions:
            # 检查会话数量限制
            if len(self.chat_sessions) >= self.max_sessions:
                self._cleanup_old_sessions()
            
            # 创建新会话
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                max_token_limit=4000  # 控制token数量
            )
            
            self.chat_sessions[session_id] = {
                "memory": memory,
                "created_at": datetime.now(),
                "last_active": datetime.now(),
                "message_count": 0
            }
            
            self.log_info(f"创建新会话: {session_id}")
        
        return session_id
    
    def _cleanup_old_sessions(self):
        """清理最老的会话"""
        # 按最后活跃时间排序，删除最老的会话
        sorted_sessions = sorted(
            self.chat_sessions.items(),
            key=lambda x: x[1]["last_active"]
        )
        
        # 删除最老的10个会话
        for session_id, _ in sorted_sessions[:10]:
            del self.chat_sessions[session_id]
            self.log_info(f"清理旧会话: {session_id}")
    
    def update_session_activity(self, session_id: str):
        """
        更新会话活跃时间
        
        Args:
            session_id: 会话ID
        """
        if session_id in self.chat_sessions:
            self.chat_sessions[session_id]["last_active"] = datetime.now()
    
    def add_to_memory(self, session_id: str, human_message: str, ai_message: str):
        """
        添加对话到记忆中
        
        Args:
            session_id: 会话ID
            human_message: 用户消息
            ai_message: AI回复消息
        """
        if session_id in self.chat_sessions:
            session = self.chat_sessions[session_id]
            memory = session["memory"]
            
            # 添加到记忆中
            memory.chat_memory.add_user_message(human_message)
            memory.chat_memory.add_ai_message(ai_message)
            
            # 更新消息计数
            session["message_count"] += 1
            
            # 如果消息数量超过限制，删除最早的消息
            if session["message_count"] > self.max_memory_length:
                messages = memory.chat_memory.messages
                if len(messages) > 4:  # 至少保留2轮对话
                    memory.chat_memory.messages = messages[2:]  # 删除最早的一轮对话
                    session["message_count"] -= 1
            
            self.log_info(f"会话 {session_id} 添加对话记录")
    
    def get_conversation_history(self, session_id: str) -> List[BaseMessage]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话历史消息列表
        """
        if session_id in self.chat_sessions:
            return self.chat_sessions[session_id]["memory"].chat_memory.messages
        return []
    
    def get_chat_sessions(self) -> Dict:
        """
        获取所有会话信息
        
        Returns:
            会话信息字典
        """
        sessions_info = {}
        for session_id, session in self.chat_sessions.items():
            sessions_info[session_id] = {
                "created_at": session["created_at"].isoformat(),
                "last_active": session["last_active"].isoformat(),
                "message_count": session["message_count"]
            }
        
        self.log_info(f"获取 {len(sessions_info)} 个会话信息")
        return sessions_info
    
    def delete_chat_session(self, session_id: str) -> bool:
        """
        删除指定会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            self.log_info(f"删除会话: {session_id}")
            return True
        
        self.log_warning(f"要删除的会话不存在: {session_id}")
        return False
    
    def clear_all_sessions(self):
        """清空所有会话"""
        session_count = len(self.chat_sessions)
        self.chat_sessions.clear()
        self.log_info(f"清空所有会话，共 {session_count} 个")
    
    def get_chat_history(self, session_id: str) -> Dict:
        """
        获取会话历史记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            格式化的历史记录
            
        Raises:
            ValueError: 会话不存在
        """
        if not session_id:
            raise ValueError("session_id is required")
        
        if session_id not in self.chat_sessions:
            raise ValueError("Session not found")
        
        history = self.get_conversation_history(session_id)
        
        # 格式化历史记录
        formatted_history = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                formatted_history.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_history.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                formatted_history.append({"role": "system", "content": msg.content})
        
        self.log_info(f"获取会话 {session_id} 历史记录，共 {len(formatted_history)} 条")
        
        return {
            "session_id": session_id,
            "history": formatted_history,
            "message_count": self.chat_sessions[session_id]["message_count"]
        }
    
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话是否存在
        """
        return session_id in self.chat_sessions