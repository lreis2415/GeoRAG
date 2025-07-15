# GeoRAG API 接口文档使用说明

## 📖 概述

GeoRAG 现在集成了 **Flasgger** 自动生成的 Swagger API 文档，提供了完整的接口文档和在线测试功能。所有接口都经过规范化处理，支持交互式文档查看和测试。

## 🚀 快速开始

### 1. 启动服务
```bash
python GeoRAGApp.py
```

### 2. 访问API文档
启动服务后，访问以下URL查看完整的API文档：

- **Swagger UI**: [http://localhost:7512/api/docs/](http://localhost:7512/api/docs/)
- **JSON规范**: [http://localhost:7512/apispec.json](http://localhost:7512/apispec.json)

## 📋 接口分类

### 1. 健康检查 (Health Check)
- **GET** `/` - 系统健康状态检查

### 2. 模型管理 (Model Management)
- **GET** `/models` - 获取可用模型列表

### 3. 数据库管理 (Database Management)
- **GET** `/databases` - 获取所有数据库列表
- **POST** `/create_db` - 创建新的向量数据库
- **POST** `/databases/add` - 向数据库添加文件
- **DELETE** `/databases/{db_name}` - 删除指定数据库

### 4. 文档管理 (Document Management)
- **GET** `/documents` - 获取所有文档列表
- **GET** `/documents/download/{filename}` - 下载指定文档
- **DELETE** `/documents/delete/{filename}` - 删除指定文档

### 5. 智能问答 (Q&A)
- **POST** `/ask` - RAG智能问答

### 6. 会话管理 (Session Management)
- **POST** `/chat` - 聊天对话（支持记忆功能）
- **GET** `/chat/sessions` - 获取所有会话信息
- **DELETE** `/chat/sessions/{session_id}` - 删除指定会话
- **POST** `/chat/sessions/clear` - 清空所有会话
- **POST** `/chat/history` - 获取会话历史记录

## 🔧 使用方法

### 1. 在线测试
1. 打开 [http://localhost:7512/api/docs/](http://localhost:7512/api/docs/)
2. 选择要测试的接口
3. 点击 "Try it out" 按钮
4. 填写必要的参数
5. 点击 "Execute" 执行请求
6. 查看响应结果

### 2. 代码示例

#### 获取模型列表
```python
import requests

response = requests.get("http://localhost:7512/models")
models = response.json()
print("可用模型:", models)
```

#### 创建数据库
```python
import requests

# 创建数据库
files = {'files': open('sample.csv', 'rb')}
data = {
    'model_name': 'text-embedding-v3',
    'db_name': 'my_knowledge_base'
}

response = requests.post(
    "http://localhost:7512/create_db",
    files=files,
    data=data
)
print("创建结果:", response.json())
```

#### RAG问答
```python
import requests

data = {
    "query": "什么是数字地形模型？",
    "db_name": "my_knowledge_base",
    "chat_model_name": "qwen-turbo"
}

response = requests.post(
    "http://localhost:7512/ask",
    json=data
)
print("AI回答:", response.json()["response"])
```

#### 带记忆的聊天
```python
import requests

# 第一轮对话
data1 = {
    "prompt": "你是一个地理信息专家助手",
    "query": "什么是数字地形模型？",
    "use_memory": True
}

response1 = requests.post("http://localhost:7512/chat", json=data1)
result1 = response1.json()
session_id = result1["session_id"]

# 第二轮对话（会记住上一轮的内容）
data2 = {
    "prompt": "你是一个地理信息专家助手",
    "query": "它有什么应用？",
    "session_id": session_id,
    "use_memory": True
}

response2 = requests.post("http://localhost:7512/chat", json=data2)
result2 = response2.json()
```

## 📝 接口规范

### 1. 请求格式
- **GET** 请求：参数通过URL传递
- **POST** 请求：
  - JSON格式：`Content-Type: application/json`
  - 文件上传：`Content-Type: multipart/form-data`

### 2. 响应格式
所有接口都返回JSON格式的响应：

```json
{
    "success": true,
    "data": {},
    "message": "操作成功"
}
```

错误响应：
```json
{
    "error": "错误描述信息"
}
```

### 3. 状态码
- **200**: 成功
- **400**: 参数错误
- **404**: 资源不存在
- **500**: 服务器内部错误

## 🛠️ 高级功能

### 1. 批量操作
支持批量上传文件到数据库：

```python
files = [
    ('files', open('file1.csv', 'rb')),
    ('files', open('file2.json', 'rb')),
    ('files', open('file3.txt', 'rb'))
]

data = {'db_name': 'my_knowledge_base'}
response = requests.post(
    "http://localhost:7512/databases/add",
    files=files,
    data=data
)
```

### 2. 会话管理
- 会话自动过期机制
- 最大会话数限制（100个）
- 单会话最大记忆轮次（20轮）

### 3. 错误处理
```python
try:
    response = requests.post("http://localhost:7512/chat", json=data)
    response.raise_for_status()  # 抛出HTTP错误
    result = response.json()
except requests.exceptions.RequestException as e:
    print(f"请求错误: {e}")
except ValueError as e:
    print(f"JSON解析错误: {e}")
```

## 🔍 调试技巧

### 1. 查看详细错误信息
启用调试模式查看详细的错误堆栈：

```python
app.debug = True  # 已在代码中启用
```

### 2. 日志记录
查看服务器日志了解详细的请求处理过程。

### 3. 使用Postman
可以导入Swagger规范到Postman中进行测试：
1. 复制 `http://localhost:7512/apispec.json` 的内容
2. 在Postman中导入OpenAPI规范
3. 自动生成所有接口的测试用例

## 📚 常见问题

### Q1: 如何查看所有可用的模型？
A: 访问 `GET /models` 接口获取完整的模型列表。

### Q2: 文件上传失败怎么办？
A: 检查文件格式（只支持CSV、JSON、TXT）和文件大小限制。

### Q3: 会话记忆不工作？
A: 确保在请求中设置 `use_memory: true` 并使用相同的 `session_id`。

### Q4: 如何重置所有会话？
A: 调用 `POST /chat/sessions/clear` 接口清空所有会话。

## 🎯 最佳实践

1. **使用会话ID**: 在连续对话中始终使用相同的session_id
2. **错误处理**: 总是检查HTTP状态码和响应中的error字段
3. **参数验证**: 在发送请求前验证必要参数
4. **资源管理**: 及时清理不需要的会话和文件
5. **性能优化**: 批量操作时注意数据量大小

---

## 🔗 相关链接

- **项目文档**: [README.md](./README.md)
- **记忆功能说明**: [记忆功能说明.md](./记忆功能说明.md)
- **Swagger官方文档**: [https://swagger.io/docs/](https://swagger.io/docs/)
- **Flasgger文档**: [https://github.com/flasgger/flasgger](https://github.com/flasgger/flasgger)

---

*最后更新: 2024-01-01* 