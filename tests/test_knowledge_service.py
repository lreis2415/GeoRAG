"""
Knowledge 服务层单元测试

测试 DatabaseService 中与知识库管理相关的全部方法。
全程使用 mock，不依赖外部服务或数据库。

使用方式：
    conda run -n gpt_ac python -m pytest tests/test_knowledge_service.py -v
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.database_service import DatabaseService

# ==================== Fixtures ====================


@pytest.fixture
def mock_dao(monkeypatch):
    """Mock DataBase DAO 层的所有函数"""
    _now = datetime.now().isoformat()

    mock_get_all = MagicMock(
        return_value=[
            {
                "id": "kb1",
                "name": "kb1",
                "embedding_model_name": "text-embedding-v4",
                "document_count": 5,
                "created_at": _now,
                "description": None,
            },
            {
                "id": "kb2",
                "name": "kb2",
                "embedding_model_name": "text-embedding-v4",
                "document_count": 0,
                "created_at": _now,
                "description": "测试知识库",
            },
        ]
    )
    mock_get_info = MagicMock(
        return_value={
            "id": "kb1",
            "name": "kb1",
            "embedding_model_name": "text-embedding-v4",
            "document_count": 5,
            "created_at": _now,
            "description": None,
        }
    )
    mock_get_files = MagicMock(
        return_value=[
            {
                "filename": "test.txt",
                "file_path": "/data/documents/test.txt",
                "file_size": 1024,
                "created_at": _now,
                "modified_at": _now,
            }
        ]
    )
    mock_create_db = MagicMock(return_value=MagicMock())
    mock_delete_db = MagicMock(return_value=True)
    mock_save_file = MagicMock(return_value="/data/documents/abc_test.txt")

    monkeypatch.setattr("app.services.database_service.get_all_databases", mock_get_all)
    monkeypatch.setattr(
        "app.services.database_service.get_database_info", mock_get_info
    )
    monkeypatch.setattr(
        "app.services.database_service.get_database_files", mock_get_files
    )
    monkeypatch.setattr("app.services.database_service.create_db", mock_create_db)
    monkeypatch.setattr("app.services.database_service.delete_database", mock_delete_db)
    monkeypatch.setattr(
        "app.services.database_service.save_uploaded_file", mock_save_file
    )

    return {
        "get_all_databases": mock_get_all,
        "get_database_info": mock_get_info,
        "get_database_files": mock_get_files,
        "create_db": mock_create_db,
        "delete_database": mock_delete_db,
        "save_uploaded_file": mock_save_file,
    }


@pytest.fixture
def service(mock_dao):
    """返回一个已注入 mock DAO 的 DatabaseService 实例"""
    return DatabaseService()


@pytest.fixture
def mock_upload_file():
    """模拟 FastAPI UploadFile 对象"""
    f = MagicMock()
    f.filename = "sample.txt"
    f.file = MagicMock()
    f.file.read.return_value = b"hello world"
    return f


# ==================== get_databases ====================


class TestGetDatabases:
    """DatabaseService.get_databases()"""

    def test_returns_databases_key(self, service, mock_dao):
        result = service.get_databases()
        assert "databases" in result

    def test_returns_list_of_dicts(self, service, mock_dao):
        result = service.get_databases()
        db_list = result["databases"]
        assert isinstance(db_list, list)
        assert len(db_list) == 2

    def test_each_item_has_required_fields(self, service, mock_dao):
        db_list = service.get_databases()["databases"]
        for item in db_list:
            for field in (
                "id",
                "name",
                "embedding_model_name",
                "document_count",
                "created_at",
            ):
                assert field in item, f"缺少字段: {field}"

    def test_calls_dao_once(self, service, mock_dao):
        service.get_databases()
        mock_dao["get_all_databases"].assert_called_once()

    def test_returns_empty_list_on_exception(self, service, mock_dao):
        mock_dao["get_all_databases"].side_effect = Exception("DB error")
        result = service.get_databases()
        assert result == {"databases": []}


# ==================== get_knowledge_base_info ====================


class TestGetKnowledgeBaseInfo:
    """DatabaseService.get_knowledge_base_info()"""

    def test_returns_dict_for_existing_kb(self, service, mock_dao):
        info = service.get_knowledge_base_info("kb1")
        assert info is not None
        assert isinstance(info, dict)

    def test_returned_dict_has_required_fields(self, service, mock_dao):
        info = service.get_knowledge_base_info("kb1")
        for field in (
            "id",
            "name",
            "embedding_model_name",
            "document_count",
            "created_at",
        ):
            assert field in info, f"缺少字段: {field}"

    def test_returns_none_for_nonexistent_kb(self, service, mock_dao):
        mock_dao["get_database_info"].return_value = None
        info = service.get_knowledge_base_info("nonexistent")
        assert info is None

    def test_calls_dao_with_correct_name(self, service, mock_dao):
        service.get_knowledge_base_info("kb1")
        mock_dao["get_database_info"].assert_called_once_with("kb1")

    def test_returns_none_on_exception(self, service, mock_dao):
        mock_dao["get_database_info"].side_effect = Exception("DB error")
        result = service.get_knowledge_base_info("kb1")
        assert result is None


# ==================== get_knowledge_base_files ====================


class TestGetKnowledgeBaseFiles:
    """DatabaseService.get_knowledge_base_files()"""

    def test_returns_list(self, service, mock_dao):
        files = service.get_knowledge_base_files("kb1")
        assert isinstance(files, list)

    def test_file_info_has_required_fields(self, service, mock_dao):
        files = service.get_knowledge_base_files("kb1")
        assert len(files) > 0
        for f in files:
            for field in (
                "filename",
                "file_path",
                "file_size",
                "created_at",
                "modified_at",
            ):
                assert field in f, f"缺少字段: {field}"

    def test_calls_dao_with_correct_name(self, service, mock_dao):
        service.get_knowledge_base_files("kb1")
        mock_dao["get_database_files"].assert_called_once_with("kb1")

    def test_returns_empty_list_on_exception(self, service, mock_dao):
        mock_dao["get_database_files"].side_effect = Exception("DB error")
        result = service.get_knowledge_base_files("kb1")
        assert result == []


# ==================== create_database ====================


class TestCreateDatabase:
    """DatabaseService.create_database()"""

    def test_create_without_files_returns_expected_keys(self, service, mock_dao):
        result = service.create_database("text-embedding-v4", "new_kb")
        for key in (
            "message",
            "db_name",
            "model_name",
            "files_processed",
            "created_at",
            "document_count",
        ):
            assert key in result, f"返回值缺少 {key}"

    def test_create_without_files_message(self, service, mock_dao):
        result = service.create_database("text-embedding-v4", "new_kb")
        assert result["message"] == "Database 'new_kb' created successfully"

    def test_create_without_files_count_is_zero(self, service, mock_dao):
        result = service.create_database("text-embedding-v4", "new_kb")
        assert result["files_processed"] == 0

    def test_create_db_name_in_vector_dbs(self, service, mock_dao):
        service.create_database("text-embedding-v4", "new_kb")
        assert "new_kb" in service.vector_dbs

    def test_create_calls_dao_create_db(self, service, mock_dao):
        service.create_database("text-embedding-v4", "new_kb")
        mock_dao["create_db"].assert_called_once()

    def test_create_with_files(self, service, mock_dao, mock_upload_file):
        result = service.create_database(
            "text-embedding-v4", "new_kb", [mock_upload_file]
        )
        assert result["files_processed"] == 1
        mock_dao["save_uploaded_file"].assert_called_once()

    def test_create_with_invalid_extension_file(self, service, mock_dao):
        invalid_file = MagicMock()
        invalid_file.filename = "test.pdf"
        invalid_file.file = MagicMock()

        result = service.create_database("text-embedding-v4", "new_kb", [invalid_file])
        # PDF 不在允许列表，files_processed 应为 0
        assert result["files_processed"] == 0
        mock_dao["save_uploaded_file"].assert_not_called()

    def test_create_raises_value_error_for_empty_model_name(self, service):
        with pytest.raises(ValueError, match="model_name is required"):
            service.create_database("", "new_kb")

    def test_create_raises_value_error_for_empty_db_name(self, service):
        with pytest.raises(ValueError, match="db_name is required"):
            service.create_database("text-embedding-v4", "")

    def test_create_raises_on_dao_exception(self, service, mock_dao):
        mock_dao["create_db"].side_effect = Exception("PG connection error")
        with pytest.raises(Exception, match="PG connection error"):
            service.create_database("text-embedding-v4", "bad_kb")


# ==================== add_files_to_database ====================


class TestAddFilesToDatabase:
    """DatabaseService.add_files_to_database()"""

    @pytest.fixture(autouse=True)
    def setup_vector_db(self, service):
        """预填充 vector_dbs 缓存"""
        mock_vdb = MagicMock()
        service.vector_dbs["existing_kb"] = mock_vdb
        self._mock_vdb = mock_vdb

    def test_add_valid_file_success(self, service, mock_dao, mock_upload_file):
        result = service.add_files_to_database("existing_kb", [mock_upload_file])
        assert result["files_processed"] == 1
        assert "existing_kb" in result["message"]

    def test_add_files_calls_vector_db_add_files(
        self, service, mock_dao, mock_upload_file
    ):
        service.add_files_to_database("existing_kb", [mock_upload_file])
        self._mock_vdb.add_files.assert_called_once()

    def test_add_files_to_nonexistent_kb_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            service.add_files_to_database("ghost_kb", [MagicMock(filename="x.txt")])

    def test_add_invalid_extension_not_saved(self, service, mock_dao):
        bad_file = MagicMock()
        bad_file.filename = "report.pdf"

        result = service.add_files_to_database("existing_kb", [bad_file])
        assert result["files_processed"] == 0
        mock_dao["save_uploaded_file"].assert_not_called()

    def test_add_empty_file_list(self, service, mock_dao):
        result = service.add_files_to_database("existing_kb", [])
        assert result["files_processed"] == 0


# ==================== delete_database ====================


class TestDeleteDatabase:
    """DatabaseService.delete_database()"""

    def test_delete_existing_kb(self, service, mock_dao):
        service.vector_dbs["kb_to_del"] = MagicMock()
        result = service.delete_database("kb_to_del")
        assert "kb_to_del" in result["message"]
        assert result["message"] == "Database 'kb_to_del' deleted successfully"

    def test_delete_removes_from_vector_dbs(self, service, mock_dao):
        service.vector_dbs["kb_to_del"] = MagicMock()
        service.delete_database("kb_to_del")
        assert "kb_to_del" not in service.vector_dbs

    def test_delete_calls_dao(self, service, mock_dao):
        service.delete_database("kb_to_del")
        mock_dao["delete_database"].assert_called_once_with("kb_to_del")

    def test_delete_nonexistent_raises_value_error(self, service, mock_dao):
        mock_dao["delete_database"].return_value = False
        with pytest.raises(ValueError, match="not found"):
            service.delete_database("nonexistent")

    def test_delete_without_cached_instance_still_calls_dao(self, service, mock_dao):
        """即使 vector_dbs 中没有缓存，也应尝试从 DAO 删除"""
        assert "uncached_kb" not in service.vector_dbs
        service.delete_database("uncached_kb")
        mock_dao["delete_database"].assert_called_once_with("uncached_kb")


# ==================== get_vector_db ====================


class TestGetVectorDb:
    """DatabaseService.get_vector_db()"""

    def test_returns_cached_instance(self, service):
        mock_vdb = MagicMock()
        service.vector_dbs["cached_kb"] = mock_vdb
        result = service.get_vector_db("cached_kb")
        assert result is mock_vdb

    def test_returns_none_when_not_in_cache_and_no_pgvector_env(
        self, service, monkeypatch
    ):
        """未缓存、USE_PGVECTOR=true 但缺少 EMBEDDING_API_URL 时应返回 None"""
        monkeypatch.setenv("USE_PGVECTOR", "true")
        monkeypatch.delenv("EMBEDDING_API_URL", raising=False)
        result = service.get_vector_db("missing_kb")
        assert result is None

    def test_loads_pgvector_and_caches(self, service, monkeypatch):
        """USE_PGVECTOR=true 且环境变量齐全时，应加载 PgvectorVectorDB 并缓存"""
        monkeypatch.setenv("USE_PGVECTOR", "true")
        monkeypatch.setenv("EMBEDDING_API_URL", "http://mock-embed")
        monkeypatch.setenv("DB_URL", "postgresql://mock:mock@localhost/mock")
        monkeypatch.setenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-v4")

        mock_vdb = MagicMock()
        # PgvectorVectorDB 在方法体内 lazy import，需要 patch 其真实所在模块
        with patch("app.dao.PgvectorVectorDB.PgvectorVectorDB", return_value=mock_vdb):
            result = service.get_vector_db("new_kb")

        assert result is mock_vdb
        assert service.vector_dbs.get("new_kb") is mock_vdb

    def test_chromadb_path_missing_returns_none(self, service, monkeypatch, tmp_path):
        """USE_PGVECTOR=false 且目录不存在时应返回 None"""
        monkeypatch.setenv("USE_PGVECTOR", "false")
        monkeypatch.setenv("EMBEDDING_API_URL", "http://mock-embed")

        with patch(
            "app.services.database_service.get_persist_directory",
            return_value=str(tmp_path / "nonexistent"),
        ):
            result = service.get_vector_db("missing_kb")

        assert result is None


# ==================== allowed_file ====================


class TestAllowedFile:
    """DatabaseService.allowed_file() 文件类型校验"""

    @pytest.mark.parametrize("filename", ["data.csv", "data.json", "data.txt"])
    def test_allowed_extensions(self, service, filename):
        assert service.allowed_file(filename) is True

    @pytest.mark.parametrize(
        "filename",
        ["doc.pdf", "image.png", "archive.zip", "sheet.xlsx", "noext"],
    )
    def test_disallowed_extensions(self, service, filename):
        assert service.allowed_file(filename) is False

    def test_case_insensitive(self, service):
        """扩展名大小写不敏感"""
        assert service.allowed_file("DATA.CSV") is True
        assert service.allowed_file("DATA.TXT") is True

    def test_empty_filename(self, service):
        assert service.allowed_file("") is False

    def test_dot_only_filename(self, service):
        assert service.allowed_file(".") is False
