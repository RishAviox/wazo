from django.test import TestCase, override_settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from unittest.mock import patch, MagicMock
import json
import tempfile
import os
from io import BytesIO


# Use in-memory storage for testing
@override_settings(
    DEFAULT_FILE_STORAGE="django.core.files.storage.FileSystemStorage",
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class TraceVisionBlobStorageTest(TestCase):
    """Test class for testing blob upload and access functionality"""

    def setUp(self):
        """Set up test data"""
        # Sample tracking data for testing
        self.sample_tracking_data = {
            "spotlights": [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "position": {"x": 10.5, "y": 20.3},
                    "speed": 5.2,
                    "distance": 15.7,
                },
                {
                    "timestamp": "2024-01-15T10:01:00Z",
                    "position": {"x": 12.1, "y": 22.8},
                    "speed": 6.1,
                    "distance": 18.2,
                },
            ],
            "metadata": {
                "total_points": 2,
                "duration_seconds": 60,
                "total_distance": 33.9,
            },
        }

        # Create a temporary local file for testing
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(self.sample_tracking_data, self.temp_file, indent=2)
        self.temp_file.close()
        self.temp_file_path = self.temp_file.name

    def test_blob_upload_with_raw_json_data(self):
        """Test uploading raw JSON data to blob storage"""
        # Create JSON content
        json_content = json.dumps(self.sample_tracking_data, indent=2)
        file_content = ContentFile(json_content.encode("utf-8"))

        # Define file path
        file_path = "tracking_data/test_session/raw_data_test.json"

        # Upload to storage
        saved_path = default_storage.save(file_path, file_content)

        # Verify file was saved
        self.assertTrue(default_storage.exists(saved_path))

        # Get the URL
        blob_url = default_storage.url(saved_path)
        self.assertIsNotNone(blob_url)

        # Verify file content
        with default_storage.open(saved_path, "r") as f:
            saved_content = f.read()
            saved_data = json.loads(saved_content)
            self.assertEqual(saved_data, self.sample_tracking_data)

    def test_blob_upload_from_local_file(self):
        """Test uploading from a local file to blob storage"""
        # Read the local file and upload to storage
        with open(self.temp_file_path, "rb") as local_file:
            file_content = ContentFile(local_file.read())
            file_path = "tracking_data/test_session/local_file_test.json"

            saved_path = default_storage.save(file_path, file_content)

            # Verify upload
            self.assertTrue(default_storage.exists(saved_path))

            # Test access
            with default_storage.open(saved_path, "r") as f:
                uploaded_data = json.loads(f.read())
                self.assertEqual(uploaded_data, self.sample_tracking_data)

    def test_blob_access_after_upload(self):
        """Test accessing blob data after upload"""
        # Upload data from local file
        with open(self.temp_file_path, "rb") as local_file:
            file_content = ContentFile(local_file.read())
            file_path = "tracking_data/test_session/access_test.json"

            saved_path = default_storage.save(file_path, file_content)
            blob_url = default_storage.url(saved_path)

        # Test reading the file
        with default_storage.open(saved_path, "r") as f:
            content = f.read()
            data = json.loads(content)

            # Verify data integrity
            self.assertEqual(len(data["spotlights"]), 2)
            self.assertEqual(data["metadata"]["total_points"], 2)
            self.assertEqual(data["spotlights"][0]["position"]["x"], 10.5)

    def test_blob_storage_file_structure(self):
        """Test the file structure and organization in blob storage"""
        # Upload multiple files to test structure
        files_to_upload = [
            ("player_1_tracking.json", {"player_id": "player_1", "data": [1, 2, 3]}),
            ("player_2_tracking.json", {"player_id": "player_2", "data": [4, 5, 6]}),
            ("session_summary.json", {"session_id": "test_session", "summary": "test"}),
        ]

        uploaded_paths = []

        for filename, data in files_to_upload:
            json_content = json.dumps(data, indent=2)
            file_content = ContentFile(json_content.encode("utf-8"))
            file_path = f"tracking_data/test_session/{filename}"

            saved_path = default_storage.save(file_path, file_content)
            uploaded_paths.append(saved_path)

            # Verify each file exists
            self.assertTrue(default_storage.exists(saved_path))

        # Verify all files are accessible
        for saved_path in uploaded_paths:
            with default_storage.open(saved_path, "r") as f:
                content = f.read()
                self.assertIsNotNone(content)

    def test_blob_storage_error_handling(self):
        """Test error handling in blob storage operations"""
        # Test with invalid JSON data
        invalid_json = "This is not valid JSON"
        file_content = ContentFile(invalid_json.encode("utf-8"))
        file_path = "tracking_data/test_session/invalid.json"

        # This should still save the file (storage doesn't validate content)
        saved_path = default_storage.save(file_path, file_content)
        self.assertTrue(default_storage.exists(saved_path))

        # Test reading invalid JSON (should raise exception)
        with self.assertRaises(json.JSONDecodeError):
            with default_storage.open(saved_path, "r") as f:
                json.loads(f.read())

    def test_blob_url_generation(self):
        """Test that blob URLs are generated correctly"""
        # Upload a test file
        json_content = json.dumps(self.sample_tracking_data, indent=2)
        file_content = ContentFile(json_content.encode("utf-8"))
        file_path = "tracking_data/test_session/url_test.json"

        saved_path = default_storage.save(file_path, file_content)
        blob_url = default_storage.url(saved_path)

        # Verify URL format
        self.assertIsNotNone(blob_url)
        self.assertTrue(blob_url.startswith("/") or blob_url.startswith("http"))

        # Verify the file can be accessed via the URL path
        if blob_url.startswith("/"):
            # For local storage, remove leading slash and check if file exists
            file_path_from_url = blob_url.lstrip("/")
            self.assertTrue(default_storage.exists(file_path_from_url))

    def tearDown(self):
        """Clean up test files"""
        # Clean up temporary file
        if hasattr(self, "temp_file_path") and os.path.exists(self.temp_file_path):
            os.unlink(self.temp_file_path)

        # Clean up any uploaded files
        try:
            # Remove test files if they exist
            for filename in os.listdir(default_storage.location):
                if filename.startswith("tracking_data"):
                    file_path = os.path.join(default_storage.location, filename)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        import shutil

                        shutil.rmtree(file_path)
        except (OSError, FileNotFoundError):
            pass
