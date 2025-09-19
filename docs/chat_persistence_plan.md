# 对话记录持久化方案 - SQLite 数据库方案

## 问题分析

当前 `ChatService` 使用内存存储会话数据，主要问题：
1. 服务重启后所有会话数据丢失
2. 多进程环境下数据不一致
3. 无法支持水平扩展

## 方案设计：SQLite 数据库持久化

### 数据库 Schema 设计

#### 1. 会话表 (chat_sessions)
```sql
CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    last_active TIMESTAMP NOT NULL,
    message_count INTEGER DEFAULT 0,
    metadata TEXT  -- JSON 格式的额外信息
);
```

#### 2. 消息表 (chat_messages)
```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    message_order INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
);
```

### 实现步骤

#### 1. 创建数据库服务模块
- 新建 `app/services/chat_database_service.py`
- 实现数据库连接和会话管理
- 提供数据持久化接口

#### 2. 修改 ChatService
- 移除内存存储逻辑
- 改用数据库服务进行数据持久化
- 保持现有 API 接口不变

#### 3. 更新依赖注入
- 在应用启动时初始化数据库
- 确保数据库连接的正确管理

### 详细实现计划

#### 第一步：数据库服务实现
```python
# app/services/chat_database_service.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

class ChatDatabaseService:
    def __init__(self, db_path: str = "chat_sessions.db"):
        self.db_path = db_path
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_database(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL,
                    last_active TIMESTAMP NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    message_order INTEGER NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_messages ON chat_messages(session_id)")
            conn.commit()
    
    def create_session(self, session_id: str) -> bool:
        with self.get_connection() as conn:
            now = datetime.now().isoformat()
            try:
                conn.execute(
                    "INSERT INTO chat_sessions (session_id, created_at, last_active) VALUES (?, ?, ?)",
                    (session_id, now, now)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return dict(row) if row else None
    
    def update_session_activity(self, session_id: str):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE chat_sessions SET last_active = ? WHERE session_id = ?",
                (datetime.now().isoformat(), session_id)
            )
            conn.commit()
    
    def add_message(self, session_id: str, role: str, content: str):
        with self.get_connection() as conn:
            now = datetime.now().isoformat()
            # 获取当前消息序号
            result = conn.execute(
                "SELECT MAX(message_order) FROM chat_messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            message_order = (result[0] or 0) + 1
            
            # 插入消息
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp, message_order) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, now, message_order)
            )
            
            # 更新会话消息计数
            conn.execute(
                "UPDATE chat_sessions SET message_count = ?, last_active = ? WHERE session_id = ?",
                (message_order, now, session_id)
            )
            conn.commit()
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY message_order",
                (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_all_sessions(self) -> List[Dict]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, last_active, message_count FROM chat_sessions ORDER BY last_active DESC"
            ).fetchall()
            return [dict(row) for row in rows]
    
    def delete_session(self, session_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def clear_all_sessions(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM chat_sessions")
            conn.commit()
```

#### 第二步：修改 ChatService
```python
# 修改 app/services/chat_service.py
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.schema.messages import BaseMessage
from .base_service import BaseService
from .chat_database_service import ChatDatabaseService

class ChatService(BaseService):
    def __init__(self, db_service: ChatDatabaseService = None):
        super().__init__()
        self.db_service = db_service or ChatDatabaseService()
        self.max_sessions = 100
        self.max_memory_length = 20
    
    def create_session(self, session_id: str = None) -> str:
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if not self.db_service.create_session(session_id):
            # 清理旧会话
            self._cleanup_old_sessions()
            # 重试创建
            if not self.db_service.create_session(session_id):
                raise ValueError(f"无法创建会话: {session_id}")
        
        self.log_info(f"创建新会话: {session_id}")
        return session_id
    
    def _cleanup_old_sessions(self):
        sessions = self.db_service.get_all_sessions()
        if len(sessions) >= self.max_sessions:
            # 删除最老的会话
            for session in sessions[-10:]:
                self.db_service.delete_session(session['session_id'])
                self.log_info(f"清理旧会话: {session['session_id']}")
    
    def session_exists(self, session_id: str) -> bool:
        return self.db_service.get_session(session_id) is not None
    
    def add_to_memory(self, session_id: str, human_message: str, ai_message: str):
        # 添加用户消息
        self.db_service.add_message(session_id, "user", human_message)
        # 添加AI回复
        self.db_service.add_message(session_id, "assistant", ai_message)
        
        # 检查消息数量限制
        session = self.db_service.get_session(session_id)
        if session and session['message_count'] > self.max_memory_length:
            self._trim_session_messages(session_id)
    
    def _trim_session_messages(self, session_id: str):
        # 删除最早的消息，保留最新的消息
        with self.db_service.get_connection() as conn:
            # 计算要保留的消息数量
            total_messages = conn.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()[0]
            
            if total_messages > self.max_memory_length * 2:  # 每轮对话2条消息
                # 删除最早的消息
                messages_to_delete = total_messages - self.max_memory_length * 2
                conn.execute(
                    "DELETE FROM chat_messages WHERE session_id = ? ORDER BY message_order LIMIT ?",
                    (session_id, messages_to_delete)
                )
                conn.commit()
    
    def get_conversation_history(self, session_id: str) -> List[BaseMessage]:
        messages = self.db_service.get_session_messages(session_id)
        history = []
        
        for msg in messages:
            if msg['role'] == 'user':
                history.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                history.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system':
                history.append(SystemMessage(content=msg['content']))
        
        return history
    
    def get_chat_history(self, session_id: str) -> Dict:
        if not session_id:
            raise ValueError("session_id is required")
        
        session = self.db_service.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        messages = self.db_service.get_session_messages(session_id)
        
        formatted_history = []
        for msg in messages:
            formatted_history.append({
                "role": msg['role'],
                "content": msg['content'],
                "timestamp": msg['timestamp']
            })
        
        self.log_info(f"获取会话 {session_id} 历史记录，共 {len(formatted_history)} 条")
        
        return {
            "session_id": session_id,
            "history": formatted_history,
            "message_count": session['message_count'],
            "created_at": session['created_at'],
            "last_active": session['last_active']
        }
    
    def get_chat_sessions(self) -> Dict:
        sessions = self.db_service.get_all_sessions()
        sessions_info = {}
        
        for session in sessions:
            sessions_info[session['session_id']] = {
                "created_at": session['created_at'],
                "last_active": session['last_active'],
                "message_count": session['message_count']
            }
        
        self.log_info(f"获取 {len(sessions_info)} 个会话信息")
        return sessions_info
    
    def delete_chat_session(self, session_id: str) -> bool:
        success = self.db_service.delete_session(session_id)
        if success:
            self.log_info(f"删除会话: {session_id}")
        else:
            self.log_warning(f"要删除的会话不存在: {session_id}")
        return success
    
    def clear_all_sessions(self):
        self.db_service.clear_all_sessions()
        self.log_info("清空所有会话")
    
    def update_session_activity(self, session_id: str):
        self.db_service.update_session_activity(session_id)
```

#### 第三步：更新依赖注入
```python
# 修改 app/utils/dependencies.py
from functools import lru_cache
from app.services import ChatService, ChatDatabaseService

@lru_cache()
def get_chat_database_service() -> ChatDatabaseService:
    """获取聊天数据库服务实例"""
    return ChatDatabaseService()

@lru_cache()
def get_chat_service() -> ChatService:
    """获取聊天服务实例"""
    db_service = get_chat_database_service()
    return ChatService(db_service)
```

#### 第四步：更新应用启动配置
```python
# 修改 main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    from app.services.chat_database_service import ChatDatabaseService
    db_service = ChatDatabaseService()
    db_service.init_database()
    
    # 初始化MCP工具
    mcp_service = MCPService()
    await mcp_service.init_mcp_tools()
    set_global_mcp_service(mcp_service)
    
    yield
    # 关闭时的清理工作（如果需要）
```

### 优势分析

1. **数据持久化**：服务重启后数据不会丢失
2. **高性能**：SQLite 轻量级，读写速度快
3. **并发安全**：支持多线程并发访问
4. **易于维护**：单一文件数据库，便于备份和管理
5. **扩展性好**：可以轻松迁移到其他数据库

### 部署注意事项

1. **数据库文件位置**：建议存储在 `data/chat_sessions.db`
2. **权限管理**：确保应用有读写权限
3. **备份策略**：定期备份数据库文件
4. **性能监控**：监控数据库文件大小和查询性能

### 测试计划

1. **单元测试**：测试所有数据库操作方法
2. **集成测试**：测试与现有 ChatService 的集成
3. **性能测试**：测试并发访问性能
4. **恢复测试**：测试服务重启后数据恢复

这个方案提供了完整的对话记录持久化解决方案，既保持了现有接口的兼容性，又提供了可靠的数据持久化能力。