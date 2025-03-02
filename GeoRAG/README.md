# GeoRAG 项目说明

## 文件夹结构
```
GeoRAG/
├── .env                # 环境变量配置文件
├── LocalVectorDB.py    # 本地向量数据库实现
├── RAGAgent.py         # RAG智能体实现
├── VectorDB.py         # 向量数据库抽象基类
├── database/           # 数据库存储目录
│   └── animals_llama3.1/
│       ├── chroma.sqlite3
│       └── e905e9c5-4859-4603-a410-3c921aac5884/
│           ├── data_level0.bin
│           ├── header.bin
│           ├── length.bin
│           └── link_lists.bin
└── documents/
    └── animals_custom.csv  # 示例CSV文档
```

## 依赖项安装指南
在使用本项目之前，请确保安装以下依赖项：

```bash
pip install -r requirements.txt
```

如果`requirements.txt`不存在，请手动安装以下依赖项：
```bash
pip install langchain langchain_community langchain_ollama langchain_openai langgraph dotenv tqdm
```

## 主要功能说明

### `LocalVectorDB.py`

#### `LocalVectorDBChroma` 类
继承自`VectorDB`，使用Chroma作为本地向量数据库的具体实现。

- **初始化参数**
  - `model_name: str`: Ollama模型名称。
  - `persist_directory: str`: 持久化存储路径。
  - `delimiter: str = ","`: CSV文件分隔符，默认为逗号。
  - `text_splitter_config: Optional[Dict] = None`: 文本分割器配置，默认为`{"chunk_size": 1000, "chunk_overlap": 200}`。

- **方法**
  - `get_vector_store()`: 返回Chroma向量存储实例。
  - `embed_documents(documents, batch_size=32)`: 分批嵌入文档。
  - `embed_csv(file_path)`: 加载并嵌入CSV文件。
  - `embed_json(file_path)`: 加载并嵌入JSON文件。
  - `embed_txt(file_path, encoding="utf-8")`: 加载并嵌入TXT文件。
  - `embed_webpage(url)`: 加载并嵌入网页。


#### `LocalVectorDBChroma` 类
继承自`VectorDB`，使用Chroma作为本地向量数据库的具体实现。

- **初始化参数**
  - `model_name: str`: Ollama模型名称。
  - `persist_directory: str`: 持久化存储路径。
  - `delimiter: str = ","`: CSV文件分隔符，默认为逗号。
  - `text_splitter_config: Optional[Dict] = None`: 文本分割器配置，默认为`{"chunk_size": 1000, "chunk_overlap": 200}`。

- **方法**
  - `get_vector_store()`: 返回Chroma向量存储实例。
  - `embed_documents(documents, batch_size=32)`: 分批嵌入文档。
  - `embed_csv(file_path)`: 加载并嵌入CSV文件。
  - `embed_json(file_path)`: 加载并嵌入JSON文件。
  - `embed_txt(file_path, encoding="utf-8")`: 加载并嵌入TXT文件。
  - `embed_webpage(url)`: 加载并嵌入网页。

### `RAGAgent.py`

#### 函数 `get_persist_directory(model_name: str) -> str`
获取向量数据库存储路径。

- **参数**
  - `model_name: str`: 模型名称。

- **返回值**
  - `str`: 持久化存储路径。

#### 函数 `create_db(model_name: str, vector_db: Optional[VectorDB] = None) -> VectorDB`
创建向量数据库。

- **参数**
  - `model_name: str`: 模型名称。
  - `vector_db: Optional[VectorDB] = None`: 可选的向量数据库实例。

- **返回值**
  - `VectorDB`: 向量数据库实例。

#### 函数 `ask_agent(...)`
运行RAG智能体。

- **参数**
  - `embed_model_name: str`: 嵌入模型名称。
  - `chat_model_name: str`: 聊天模型名称。
  - `query: str`: 查询字符串。
  - `use_api: bool = False`: 是否使用API。
  - `api_key: Optional[str] = None`: API密钥。
  - `api_base: Optional[str] = None`: API基础URL。
  - `vector_db: Optional[VectorDB] = None`: 可选的向量数据库实例。

#### 函数 `test_model(...)`
测试模型。

- **参数**
  - `embed_model_name: str`: 嵌入模型名称。
  - `chat_model_name: str`: 聊天模型名称。
  - `use_api: bool = False`: 是否使用API。
  - `api_key: Optional[str] = None`: API密钥。
  - `api_base: Optional[str] = None`: API基础URL。

## 使用示例

### 创建向量数据库
```python
from RAGAgent import create_db

db = create_db("llama3.1")
```

### 运行RAG智能体
```python
from RAGAgent import ask_agent

ask_agent(
    embed_model_name="llama3.1",
    chat_model_name="qwen-turbo",
    query="羊的学名是什么？它对人类有什么用处？",
    use_api=True,
    api_key="your_api_key",
    api_base="your_api_base"
)
```

### 测试模型
```python
from RAGAgent import test_model

test_model(
    embed_model_name="llama3.1",
    chat_model_name="qwen-turbo",
    use_api=True,
    api_key="your_api_key",
    api_base="your_api_base"
)
```

## 结论
本项目提供了一个完整的框架，用于构建基于本地向量数据库的RAG智能体。通过上述说明和示例，用户可以快速上手并扩展本项目以满足具体需求。