from GeoRAG.FlexibleVectorDB import FlexibleVectorDB
from langchain_core.documents import Document

# 测试配置
import os

# 从环境变量和配置文件中读取嵌入模型信息
EMBEDDING_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "text-embedding-v3"  # 默认嵌入模型名称
PERSIST_DIRECTORY = "./test_data"

# 创建 FlexibleVectorDB 实例
flexible_db = FlexibleVectorDB(
    embedding_api_url=EMBEDDING_API_URL,
    model_name=MODEL_NAME,
    persist_directory=PERSIST_DIRECTORY
)

# 测试文档
test_documents = [
    Document(page_content="这是测试文档1。"),
    Document(page_content="这是测试文档2。")
]

# 测试嵌入文档功能
def test_embed_documents():
    try:
        # 调试：
        embeddings = flexible_db.embed_documents(test_documents)
        print("Embeddings:", embeddings)
        flexible_db.embed_documents(test_documents)
        print("嵌入文档测试成功！")
    except Exception as e:
        print(f"嵌入文档测试失败: {e}")

# 运行测试
if __name__ == "__main__":
    test_embed_documents()