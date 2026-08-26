"""
Knowledge 模块集成测试

测试 /llm/v1/knowledge/* 的所有接口，需要服务处于运行状态。

使用方式：
    # 默认启用日志
    pytest tests/test_knowledge_api.py -v -s

    # 禁用日志
    pytest tests/test_knowledge_api.py -v -s --no-log

    # 只跑某个类
    pytest tests/test_knowledge_api.py::TestKnowledgeBaseAPI -v -s
"""

import logging
from datetime import datetime
from pathlib import Path

import pytest
import requests

# ==================== 日志配置 ====================

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = (
    LOG_DIR / f"test_knowledge_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_logging_enabled = True


def _setup_logger() -> None:
    logger.handlers.clear()
    fh = logging.FileHandler(log_file, encoding="utf-8")
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.propagate = False


_setup_logger()


@pytest.fixture(scope="session", autouse=True)
def configure_logging(request):
    if request.config.getoption("--no-log"):
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())


# ==================== 常量 ====================

BASE_URL = "http://0.0.0.0:7512/llm/v1"
KNOWLEDGE_BASE_URL = f"{BASE_URL}/knowledge/bases"
KNOWLEDGE_FILE_URL = f"{BASE_URL}/knowledge/files"

# 测试用知识库名（带时间戳保证唯一）
_TS = datetime.now().strftime("%H%M%S")
TEST_KB_NAME = f"test_kb_{_TS}"
TEST_EMBED_MODEL = "text-embedding-v4"


# ==================== Session 级 Fixture ====================


@pytest.fixture(scope="session", autouse=True)
def check_service_running():
    """跳过测试当服务未运行时"""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip("GeoRAG 服务未运行，请先执行: python main.py")
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip("无法连接到 GeoRAG 服务，请确保服务正在运行")


# ==================== 工具函数 ====================


def _assert_standard_response(resp: requests.Response, expect_success: bool = True):
    """断言响应符合 StandardResponse 格式"""
    assert (
        resp.status_code == 200
    ), f"HTTP 状态码错误: {resp.status_code}, body={resp.text}"
    body = resp.json()
    assert "success" in body, "缺少 success 字段"
    assert "code" in body, "缺少 code 字段"
    assert "message" in body, "缺少 message 字段"
    assert "data" in body, "缺少 data 字段"
    if expect_success:
        assert (
            body["success"] is True
        ), f"操作失败: code={body['code']}, msg={body['message']}"
    return body


# ==================== 知识库管理接口测试 ====================


class TestKnowledgeBaseAPI:
    """
    知识库 CRUD 全流程测试

    执行顺序：01 创建 → 02 列表验证 → 03 详情 → 04 文件列表 → 05 删除
    """

    # 跨测试共享的知识库名
    _created_kb: str = ""

    # ------------------------------------------------------------------
    # 01. 创建知识库（不带文件）
    # ------------------------------------------------------------------

    def test_01_create_knowledge_base_no_files(self):
        """POST /knowledge/bases — 创建不含文件的知识库"""
        logger.info("=" * 70)
        logger.info("test_01_create_knowledge_base_no_files")

        resp = requests.post(
            KNOWLEDGE_BASE_URL,
            data={"model_name": TEST_EMBED_MODEL, "db_name": TEST_KB_NAME},
        )
        body = _assert_standard_response(resp)

        data = body["data"]
        assert data["db_name"] == TEST_KB_NAME, "db_name 不匹配"
        assert data["model_name"] == TEST_EMBED_MODEL, "model_name 不匹配"
        assert data["files_processed"] == 0, "未传文件时 files_processed 应为 0"
        assert "created_at" in data, "缺少 created_at"
        assert "document_count" in data, "缺少 document_count"
        assert body["message"] == "知识库创建成功"

        TestKnowledgeBaseAPI._created_kb = TEST_KB_NAME
        logger.info(f"✅ 知识库已创建: {TEST_KB_NAME}")

    # ------------------------------------------------------------------
    # 02. 列表接口 — 验证新建知识库出现在列表中
    # ------------------------------------------------------------------

    def test_02_list_knowledge_bases_contains_created(self):
        """GET /knowledge/bases — 列表中应包含刚创建的知识库"""
        logger.info("=" * 70)
        logger.info("test_02_list_knowledge_bases_contains_created")

        if not TestKnowledgeBaseAPI._created_kb:
            pytest.skip("依赖 test_01，请按顺序执行")

        resp = requests.get(KNOWLEDGE_BASE_URL)
        body = _assert_standard_response(resp)

        data = body["data"]
        assert "databases" in data, "缺少 databases 字段"
        db_list = data["databases"]
        assert isinstance(db_list, list), "databases 应为列表"

        names = [db.get("id") or db.get("name") for db in db_list]
        assert (
            TestKnowledgeBaseAPI._created_kb in names
        ), f"知识库 {TestKnowledgeBaseAPI._created_kb} 未出现在列表中，当前: {names}"

        # 验证列表中每条记录的字段完整性
        for db in db_list:
            if (db.get("id") or db.get("name")) == TestKnowledgeBaseAPI._created_kb:
                assert "embedding_model_name" in db, "缺少 embedding_model_name"
                assert "document_count" in db, "缺少 document_count"
                assert "created_at" in db, "缺少 created_at"
                logger.info(f"✅ 找到知识库记录: {db}")
                break

    # ------------------------------------------------------------------
    # 03. 详情接口
    # ------------------------------------------------------------------

    def test_03_get_knowledge_base_detail(self):
        """GET /knowledge/bases/{db_name} — 获取单个知识库详情"""
        logger.info("=" * 70)
        logger.info("test_03_get_knowledge_base_detail")

        if not TestKnowledgeBaseAPI._created_kb:
            pytest.skip("依赖 test_01，请按顺序执行")

        kb = TestKnowledgeBaseAPI._created_kb
        resp = requests.get(f"{KNOWLEDGE_BASE_URL}/{kb}")
        body = _assert_standard_response(resp)

        data = body["data"]
        assert data["id"] == kb, f"id 不匹配，期望 {kb}，实际 {data.get('id')}"
        assert data["embedding_model_name"] == TEST_EMBED_MODEL
        assert isinstance(data["document_count"], int)
        assert isinstance(data["created_at"], str) and len(data["created_at"]) > 0
        logger.info(f"✅ 详情正确: {data}")

    def test_03b_get_nonexistent_knowledge_base(self):
        """GET /knowledge/bases/{db_name} — 查询不存在的知识库应返回错误"""
        logger.info("test_03b_get_nonexistent_knowledge_base")

        resp = requests.get(f"{KNOWLEDGE_BASE_URL}/nonexistent_kb_xyz_999")
        body = _assert_standard_response(resp, expect_success=False)
        assert body["success"] is False
        assert body["code"] == 4004
        logger.info(f"✅ 正确返回 404: {body['message']}")

    # ------------------------------------------------------------------
    # 04. 文件列表接口
    # ------------------------------------------------------------------

    def test_04_get_knowledge_base_files_empty(self):
        """GET /knowledge/bases/{db_name}/files — 新建知识库文件列表应为空"""
        logger.info("=" * 70)
        logger.info("test_04_get_knowledge_base_files_empty")

        if not TestKnowledgeBaseAPI._created_kb:
            pytest.skip("依赖 test_01，请按顺序执行")

        kb = TestKnowledgeBaseAPI._created_kb
        resp = requests.get(f"{KNOWLEDGE_BASE_URL}/{kb}/files")
        body = _assert_standard_response(resp)

        data = body["data"]
        assert "db_name" in data, "缺少 db_name"
        assert "files" in data, "缺少 files"
        assert "total_count" in data, "缺少 total_count"
        assert data["db_name"] == kb
        assert isinstance(data["files"], list)
        assert data["total_count"] == len(data["files"])
        logger.info(f"✅ 文件列表正确（空）: total_count={data['total_count']}")

    def test_04b_get_files_of_nonexistent_kb(self):
        """GET /knowledge/bases/{db_name}/files — 不存在的知识库应返回 4004"""
        logger.info("test_04b_get_files_of_nonexistent_kb")

        resp = requests.get(f"{KNOWLEDGE_BASE_URL}/nonexistent_kb_xyz_999/files")
        body = _assert_standard_response(resp, expect_success=False)
        assert body["code"] == 4004
        logger.info(f"✅ 正确返回 404: {body['message']}")

    # ------------------------------------------------------------------
    # 05. 删除知识库
    # ------------------------------------------------------------------

    def test_05_delete_knowledge_base(self):
        """DELETE /knowledge/bases/{db_name} — 删除已创建的知识库"""
        logger.info("=" * 70)
        logger.info("test_05_delete_knowledge_base")

        if not TestKnowledgeBaseAPI._created_kb:
            pytest.skip("依赖 test_01，请按顺序执行")

        kb = TestKnowledgeBaseAPI._created_kb
        resp = requests.delete(f"{KNOWLEDGE_BASE_URL}/{kb}")
        body = _assert_standard_response(resp)

        assert body["message"] == "知识库删除成功"
        logger.info(f"✅ 知识库已删除: {kb}")

    def test_05b_deleted_kb_no_longer_in_list(self):
        """GET /knowledge/bases — 删除后知识库不应再出现在列表中"""
        logger.info("test_05b_deleted_kb_no_longer_in_list")

        if not TestKnowledgeBaseAPI._created_kb:
            pytest.skip("依赖 test_05，请按顺序执行")

        kb = TestKnowledgeBaseAPI._created_kb
        resp = requests.get(KNOWLEDGE_BASE_URL)
        body = _assert_standard_response(resp)

        names = [
            db.get("id") or db.get("name") for db in body["data"].get("databases", [])
        ]
        assert kb not in names, f"已删除的知识库 {kb} 仍出现在列表中"
        logger.info(f"✅ 确认 {kb} 已从列表中移除")

    def test_05c_delete_nonexistent_knowledge_base(self):
        """DELETE /knowledge/bases/{db_name} — 删除不存在的知识库应返回错误"""
        logger.info("test_05c_delete_nonexistent_knowledge_base")

        resp = requests.delete(f"{KNOWLEDGE_BASE_URL}/nonexistent_kb_xyz_999")
        body = _assert_standard_response(resp, expect_success=False)
        assert body["success"] is False
        logger.info(f"✅ 正确返回错误: code={body['code']}, msg={body['message']}")


# ==================== 创建参数校验测试 ====================


class TestKnowledgeBaseCreateValidation:
    """POST /knowledge/bases 参数校验"""

    def test_missing_model_name(self):
        """缺少 model_name 应返回错误（422 或业务错误）"""
        logger.info("test_missing_model_name")
        resp = requests.post(
            KNOWLEDGE_BASE_URL,
            data={"db_name": "test_no_model"},
        )
        # 422 表示 FastAPI 参数校验失败，或者业务层返回 4000
        assert resp.status_code in (200, 422), f"意外状态码: {resp.status_code}"
        if resp.status_code == 200:
            body = resp.json()
            assert body["success"] is False
        logger.info(f"✅ 正确拒绝: status={resp.status_code}")

    def test_missing_db_name(self):
        """缺少 db_name 应返回错误"""
        logger.info("test_missing_db_name")
        resp = requests.post(
            KNOWLEDGE_BASE_URL,
            data={"model_name": TEST_EMBED_MODEL},
        )
        assert resp.status_code in (200, 422)
        if resp.status_code == 200:
            body = resp.json()
            assert body["success"] is False
        logger.info(f"✅ 正确拒绝: status={resp.status_code}")

    def test_invalid_embedding_model(self):
        """使用不存在的嵌入模型应返回 4000"""
        logger.info("test_invalid_embedding_model")
        resp = requests.post(
            KNOWLEDGE_BASE_URL,
            data={
                "model_name": "nonexistent-embedding-model-xyz",
                "db_name": f"test_invalid_model_{_TS}",
            },
        )
        body = _assert_standard_response(resp, expect_success=False)
        assert body["success"] is False
        assert body["code"] == 4000, f"期望 4000，实际 {body['code']}"
        logger.info(f"✅ 正确返回 4000: {body['message']}")


# ==================== 知识文件管理接口测试 ====================


class TestKnowledgeFilesAPI:
    """
    知识文件管理接口测试

    GET  /knowledge/files            — 文件列表
    GET  /knowledge/files/{fn}/download — 下载文件
    DELETE /knowledge/files/{fn}    — 删除文件
    """

    def test_list_knowledge_files(self):
        """GET /knowledge/files — 获取所有知识文件列表"""
        logger.info("=" * 70)
        logger.info("test_list_knowledge_files")

        resp = requests.get(KNOWLEDGE_FILE_URL)
        body = _assert_standard_response(resp)

        data = body["data"]
        # data 可能是 list 或 dict（包含 documents 键）
        if isinstance(data, list):
            files = data
        elif isinstance(data, dict):
            files = data.get("documents", data.get("files", []))
        else:
            files = []

        assert isinstance(files, list), f"文件列表应为 list，实际: {type(files)}"
        logger.info(f"✅ 文件列表返回正常，共 {len(files)} 个文件")

    def test_download_nonexistent_file(self):
        """GET /knowledge/files/{filename}/download — 下载不存在的文件应返回错误"""
        logger.info("test_download_nonexistent_file")

        resp = requests.get(f"{KNOWLEDGE_FILE_URL}/nonexistent_file_xyz.txt/download")
        # 服务返回 200（标准响应）或 404
        if resp.status_code == 200:
            body = resp.json()
            assert body["success"] is False
            assert body["code"] == 4004
        else:
            assert resp.status_code == 404
        logger.info(f"✅ 正确处理不存在文件: status={resp.status_code}")

    def test_delete_nonexistent_file(self):
        """DELETE /knowledge/files/{filename} — 删除不存在的文件应返回错误"""
        logger.info("test_delete_nonexistent_file")

        resp = requests.delete(f"{KNOWLEDGE_FILE_URL}/nonexistent_file_xyz.txt")
        if resp.status_code == 200:
            body = resp.json()
            assert body["success"] is False
            assert body["code"] == 4004
        else:
            assert resp.status_code == 404
        logger.info(f"✅ 正确处理不存在文件: status={resp.status_code}")


# ==================== 响应结构一致性测试 ====================


class TestResponseStructure:
    """验证所有 knowledge 接口都返回统一的 StandardResponse 格式"""

    _endpoints = [
        ("GET", KNOWLEDGE_BASE_URL, None),
        ("GET", f"{KNOWLEDGE_FILE_URL}", None),
    ]

    @pytest.mark.parametrize("method,url,payload", _endpoints)
    def test_standard_response_format(self, method, url, payload):
        """验证接口返回标准响应格式"""
        logger.info(f"test_standard_response_format: {method} {url}")

        if method == "GET":
            resp = requests.get(url)
        else:
            resp = requests.post(url, json=payload)

        assert resp.status_code == 200, f"HTTP 状态码错误: {resp.status_code}"
        body = resp.json()

        for field in ("success", "code", "message", "data"):
            assert field in body, f"{url} 响应缺少字段: {field}"

        assert isinstance(body["success"], bool)
        assert isinstance(body["code"], int)
        assert isinstance(body["message"], str)
        logger.info(f"✅ 响应格式正确: success={body['success']}, code={body['code']}")


# ==================== 主函数 ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
