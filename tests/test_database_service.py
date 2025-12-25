"""
Tests for database_service.py
"""

from unittest.mock import MagicMock

import pytest
from werkzeug.datastructures import FileStorage

from app.services.database_service import DatabaseService


@pytest.fixture
def mock_files():
    """创建测试用的模拟文件"""
    return [
        MagicMock(spec=FileStorage, filename="test1.txt"),
        MagicMock(spec=FileStorage, filename="test2.txt"),
    ]


@pytest.fixture
def mock_db_operations(monkeypatch):
    """Mock 数据库操作函数"""
    mock_create_db = MagicMock(return_value=MagicMock())
    mock_delete_database = MagicMock(return_value=True)
    mock_get_all_databases = MagicMock(return_value=["db1", "db2"])
    mock_save_uploaded_file = MagicMock(return_value="/tmp/test_file.txt")

    monkeypatch.setattr("app.services.database_service.create_db", mock_create_db)
    monkeypatch.setattr(
        "app.services.database_service.delete_database", mock_delete_database
    )
    monkeypatch.setattr(
        "app.services.database_service.get_all_databases", mock_get_all_databases
    )
    monkeypatch.setattr(
        "app.services.database_service.save_uploaded_file", mock_save_uploaded_file
    )

    return {
        "create_db": mock_create_db,
        "delete_database": mock_delete_database,
        "get_all_databases": mock_get_all_databases,
        "save_uploaded_file": mock_save_uploaded_file,
    }


@pytest.fixture
def mock_uuid(monkeypatch):
    """Mock uuid.uuid4"""
    mock_uuid = MagicMock()
    mock_uuid.return_value.hex = "testuuid"
    monkeypatch.setattr("uuid.uuid4", mock_uuid)
    return mock_uuid


@pytest.fixture
def mock_secure_filename(monkeypatch):
    """Mock werkzeug.utils.secure_filename"""
    mock_fn = MagicMock(return_value="test.txt")
    monkeypatch.setattr("werkzeug.utils.secure_filename", mock_fn)
    return mock_fn


@pytest.fixture
def service(mock_db_operations):
    """创建 DatabaseService 实例"""
    return DatabaseService()


# ==================== 测试文件类型验证 ====================


def test_allowed_file_valid(service):
    """测试有效文件扩展名"""
    assert service.allowed_file("test.csv") is True
    assert service.allowed_file("test.json") is True
    assert service.allowed_file("test.txt") is True


def test_allowed_file_invalid(service):
    """测试无效文件扩展名"""
    assert service.allowed_file("test.pdf") is False
    assert service.allowed_file("test.doc") is False
    assert service.allowed_file("test") is False


# ==================== 测试获取数据库列表 ====================


def test_get_databases_success(service, mock_db_operations):
    """测试成功获取数据库列表"""
    result = service.get_databases()
    assert result == {"databases": ["db1", "db2"]}
    mock_db_operations["get_all_databases"].assert_called_once()


def test_get_databases_exception(service, mock_db_operations):
    """测试获取数据库列表时的异常处理"""
    mock_db_operations["get_all_databases"].side_effect = Exception("DB Error")
    result = service.get_databases()
    assert result == {"databases": []}


# ==================== 测试创建数据库 ====================


def test_create_database_success(service, mock_db_operations, mock_files, monkeypatch):
    """测试成功创建数据库"""
    monkeypatch.setattr("os.path.exists", lambda x: True)

    result = service.create_database(
        model_name="test_model",
        db_name="test_db",
        files=mock_files,
    )

    assert result["message"] == "Database 'test_db' created successfully"
    assert result["db_name"] == "test_db"
    assert result["model_name"] == "test_model"
    assert result["files_processed"] == 2
    mock_db_operations["create_db"].assert_called_once()


def test_create_database_missing_model_name(service):
    """测试缺少 model_name 参数"""
    with pytest.raises(ValueError) as exc_info:
        service.create_database("", "test_db")
    assert str(exc_info.value) == "model_name is required"


def test_create_database_missing_db_name(service):
    """测试缺少 db_name 参数"""
    with pytest.raises(ValueError) as exc_info:
        service.create_database("test_model", "")
    assert str(exc_info.value) == "db_name is required"


# ==================== 测试添加文件到数据库 ====================


def test_add_files_to_database_success(service, mock_files):
    """测试成功添加文件到数据库"""
    test_db_name = "test_db"
    mock_vector_db = MagicMock()
    service.vector_dbs[test_db_name] = mock_vector_db

    result = service.add_files_to_database(db_name=test_db_name, files=mock_files)

    assert result["message"] == f"Files added to database '{test_db_name}' successfully"
    assert result["files_processed"] == 2
    mock_vector_db.add_files.assert_called_once()


def test_add_files_to_nonexistent_database(service):
    """测试向不存在的数据库添加文件"""
    with pytest.raises(ValueError) as exc_info:
        service.add_files_to_database("nonexistent", [])
    assert "not found" in str(exc_info.value)


# ==================== 测试删除数据库 ====================


def test_delete_database_success(service, mock_db_operations):
    """测试成功删除数据库"""
    test_db_name = "test_db"
    service.vector_dbs[test_db_name] = MagicMock()

    result = service.delete_database(test_db_name)

    assert result["message"] == f"Database '{test_db_name}' deleted successfully"
    mock_db_operations["delete_database"].assert_called_once_with(test_db_name)
    assert test_db_name not in service.vector_dbs


def test_delete_nonexistent_database(service, mock_db_operations):
    """测试删除不存在的数据库"""
    mock_db_operations["delete_database"].return_value = False

    with pytest.raises(ValueError) as exc_info:
        service.delete_database("nonexistent")
    assert "not found" in str(exc_info.value)


# ==================== 测试获取向量数据库实例 ====================


def test_get_vector_db(service):
    """测试获取向量数据库实例"""
    test_db_name = "test_db"
    test_vector = MagicMock()
    service.vector_dbs[test_db_name] = test_vector

    result = service.get_vector_db(test_db_name)
    assert result == test_vector

    # 测试不存在的数据库
    assert service.get_vector_db("nonexistent") is None
