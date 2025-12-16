"""
Tests for database_service.py
"""

import unittest
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage

from app.services.database_service import DatabaseService


class TestDatabaseService(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.service = DatabaseService()
        self.test_db_name = "test_db"
        self.test_model_name = "test_model"
        self.test_files = [
            MagicMock(spec=FileStorage, filename="test1.txt"),
            MagicMock(spec=FileStorage, filename="test2.txt"),
        ]

        # Mock the database operations
        # 注意：DatabaseService 在 app.services.database_service 中通过
        # "from app.dao.DataBase import xxx" 导入函数
        # 因此需要 patch 使用它们的模块，而不是定义它们的模块
        self.mock_create_db = patch("app.services.database_service.create_db").start()
        self.mock_delete_database = patch(
            "app.services.database_service.delete_database"
        ).start()
        self.mock_get_all_databases = patch(
            "app.services.database_service.get_all_databases"
        ).start()
        self.mock_save_uploaded_file = patch(
            "app.services.database_service.save_uploaded_file"
        ).start()

        # Setup default return values
        self.mock_create_db.return_value = MagicMock()
        self.mock_delete_database.return_value = True
        self.mock_get_all_databases.return_value = ["db1", "db2"]
        self.mock_save_uploaded_file.return_value = "/tmp/test_file.txt"

        # Mock uuid
        self.mock_uuid = patch("uuid.uuid4").start()
        self.mock_uuid.return_value.hex = "testuuid"

        # Mock secure_filename
        self.mock_secure_filename = patch("werkzeug.utils.secure_filename").start()
        self.mock_secure_filename.return_value = "test.txt"

    def tearDown(self):
        """Clean up after each test method."""
        patch.stopall()

    def test_allowed_file_valid(self):
        """Test allowed_file with valid file extensions."""
        self.assertTrue(self.service.allowed_file("test.csv"))
        self.assertTrue(self.service.allowed_file("test.json"))
        self.assertTrue(self.service.allowed_file("test.txt"))

    def test_allowed_file_invalid(self):
        """Test allowed_file with invalid file extensions."""
        self.assertFalse(self.service.allowed_file("test.pdf"))
        self.assertFalse(self.service.allowed_file("test.doc"))
        self.assertFalse(self.service.allowed_file("test"))

    def test_get_databases_success(self):
        """Test successful retrieval of database list."""
        result = self.service.get_databases()
        self.assertEqual(result, {"databases": ["db1", "db2"]})
        self.mock_get_all_databases.assert_called_once()

    def test_get_databases_exception(self):
        """Test exception handling in get_databases."""
        self.mock_get_all_databases.side_effect = Exception("DB Error")
        result = self.service.get_databases()
        self.assertEqual(result, {"databases": []})

    def test_create_database_success(self):
        """Test successful database creation with files."""
        with patch("os.path.exists", return_value=True):
            result = self.service.create_database(
                model_name=self.test_model_name,
                db_name=self.test_db_name,
                files=self.test_files,
            )

        self.assertEqual(
            result["message"], f"Database '{self.test_db_name}' created successfully"
        )
        self.assertEqual(result["db_name"], self.test_db_name)
        self.assertEqual(result["model_name"], self.test_model_name)
        self.assertEqual(result["files_processed"], 2)
        self.mock_create_db.assert_called_once()

    def test_create_database_missing_params(self):
        """Test database creation with missing parameters."""
        with self.assertRaises(ValueError) as context:
            self.service.create_database("", self.test_db_name)
        self.assertEqual(str(context.exception), "model_name is required")

        with self.assertRaises(ValueError) as context:
            self.service.create_database(self.test_model_name, "")
        self.assertEqual(str(context.exception), "db_name is required")

    def test_add_files_to_database_success(self):
        """Test adding files to an existing database."""
        # Setup
        self.service.vector_dbs[self.test_db_name] = MagicMock()
        self.service.vector_dbs[self.test_db_name].add_files = MagicMock()

        # Test
        result = self.service.add_files_to_database(
            db_name=self.test_db_name, files=self.test_files
        )

        # Assert
        self.assertEqual(
            result["message"],
            f"Files added to database '{self.test_db_name}' successfully",
        )
        self.assertEqual(result["files_processed"], 2)
        self.service.vector_dbs[self.test_db_name].add_files.assert_called_once()

    def test_add_files_to_nonexistent_database(self):
        """Test adding files to a non-existent database."""
        with self.assertRaises(ValueError) as context:
            self.service.add_files_to_database("nonexistent", [])
        self.assertIn("not found", str(context.exception))

    def test_delete_database_success(self):
        """Test successful database deletion."""
        self.service.vector_dbs[self.test_db_name] = MagicMock()
        result = self.service.delete_database(self.test_db_name)
        self.assertEqual(
            result["message"], f"Database '{self.test_db_name}' deleted successfully"
        )
        self.mock_delete_database.assert_called_once_with(self.test_db_name)
        self.assertNotIn(self.test_db_name, self.service.vector_dbs)

    def test_delete_nonexistent_database(self):
        """Test deleting a non-existent database."""
        self.mock_delete_database.return_value = False
        with self.assertRaises(ValueError) as context:
            self.service.delete_database("nonexistent")
        self.assertIn("not found", str(context.exception))

    def test_get_vector_db(self):
        """Test getting a vector database instance."""
        test_vector = MagicMock()
        self.service.vector_dbs[self.test_db_name] = test_vector
        result = self.service.get_vector_db(self.test_db_name)
        self.assertEqual(result, test_vector)

        # Test non-existent database
        self.assertIsNone(self.service.get_vector_db("nonexistent"))


if __name__ == "__main__":
    unittest.main()
