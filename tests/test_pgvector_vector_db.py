"""Regression tests for pgvector knowledge-base initialization."""

from unittest.mock import MagicMock

from app.dao.PgvectorVectorDB import PgvectorVectorDB


def test_metadata_initializes_pgvector_before_executing_update(monkeypatch):
    """A new database must create LangChain tables before raw SQL uses them."""
    vector_db = object.__new__(PgvectorVectorDB)
    vector_db._connection_string = "postgresql+psycopg://unused"
    vector_db._db_name = "new_kb"

    call_order = []
    mock_store = MagicMock(side_effect=lambda: call_order.append("store"))
    monkeypatch.setattr(vector_db, "get_vector_store", mock_store)

    mock_result = MagicMock(rowcount=1)
    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_result
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.side_effect = lambda: (
        call_order.append("begin") or mock_engine.begin.return_value
    )
    monkeypatch.setattr("sqlalchemy.create_engine", lambda _: mock_engine)

    vector_db.update_collection_metadata({"name": "new_kb"})

    assert call_order == ["store", "begin"]
    mock_conn.execute.assert_called_once()


def test_metadata_update_fails_when_pgvector_did_not_create_collection(monkeypatch):
    """Do not report a knowledge base as created if its collection is absent."""
    vector_db = object.__new__(PgvectorVectorDB)
    vector_db._connection_string = "postgresql+psycopg://unused"
    vector_db._db_name = "missing_kb"
    monkeypatch.setattr(vector_db, "get_vector_store", MagicMock())

    mock_conn = MagicMock()
    mock_conn.execute.return_value = MagicMock(rowcount=0)
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    monkeypatch.setattr("sqlalchemy.create_engine", lambda _: mock_engine)

    try:
        vector_db.update_collection_metadata({"name": "missing_kb"})
    except RuntimeError as exc:
        assert "未创建" in str(exc)
    else:
        raise AssertionError("Expected metadata update to fail")
