"""Tests for sync.state — state serialization/deserialization with mocked Azure Blob."""

import json
from unittest.mock import patch, MagicMock

from sync.state import load_state, save_state, CONTAINER_NAME, BLOB_NAME


def _mock_blob_infra(existing_data: dict | None = None):
    """Create mock Azure Blob infrastructure.

    Returns (mock_blob_client, mock_container_client, mock_service).
    """
    mock_blob_client = MagicMock()
    mock_container_client = MagicMock()
    mock_service = MagicMock()

    mock_service.get_container_client.return_value = mock_container_client
    mock_container_client.get_blob_client.return_value = mock_blob_client

    if existing_data is not None:
        mock_blob_client.download_blob.return_value.readall.return_value = json.dumps(existing_data).encode()
    else:
        mock_blob_client.download_blob.side_effect = Exception("BlobNotFound")

    return mock_blob_client, mock_container_client, mock_service


class TestLoadState:
    @patch("sync.state.BlobServiceClient")
    def test_loads_existing_state(self, mock_bsc_class):
        state_data = {
            "uid-001": {"google_id": "g-123", "sequence": 3, "last_modified": "2026-03-18T14:00:00+00:00"},
            "uid-002": {"google_id": "g-456", "sequence": 0, "last_modified": ""},
        }
        mock_blob, mock_container, mock_service = _mock_blob_infra(state_data)
        mock_bsc_class.from_connection_string.return_value = mock_service

        result = load_state("fake-connection-string")

        assert result == state_data
        assert len(result) == 2
        mock_service.get_container_client.assert_called_once_with(CONTAINER_NAME)
        mock_container.get_blob_client.assert_called_once_with(BLOB_NAME)

    @patch("sync.state.BlobServiceClient")
    def test_returns_empty_dict_when_no_state(self, mock_bsc_class):
        """First run: no state blob exists, should return empty dict."""
        mock_blob, mock_container, mock_service = _mock_blob_infra(None)
        mock_bsc_class.from_connection_string.return_value = mock_service

        result = load_state("fake-connection-string")

        assert result == {}

    @patch("sync.state.BlobServiceClient")
    def test_loads_empty_state(self, mock_bsc_class):
        """State file exists but is empty dict."""
        mock_blob, mock_container, mock_service = _mock_blob_infra({})
        mock_bsc_class.from_connection_string.return_value = mock_service

        result = load_state("fake-connection-string")

        assert result == {}


class TestSaveState:
    @patch("sync.state.BlobServiceClient")
    def test_saves_state_as_json(self, mock_bsc_class):
        state_data = {
            "uid-001": {"google_id": "g-123", "sequence": 3, "last_modified": ""},
        }
        mock_blob, mock_container, mock_service = _mock_blob_infra()
        mock_bsc_class.from_connection_string.return_value = mock_service

        save_state("fake-connection-string", state_data)

        mock_blob.upload_blob.assert_called_once()
        call_args = mock_blob.upload_blob.call_args
        saved_json = call_args[0][0]
        assert json.loads(saved_json) == state_data
        assert call_args[1]["overwrite"] is True

    @patch("sync.state.BlobServiceClient")
    def test_saves_empty_state(self, mock_bsc_class):
        mock_blob, mock_container, mock_service = _mock_blob_infra()
        mock_bsc_class.from_connection_string.return_value = mock_service

        save_state("fake-connection-string", {})

        call_args = mock_blob.upload_blob.call_args
        assert json.loads(call_args[0][0]) == {}

    @patch("sync.state.BlobServiceClient")
    def test_creates_container_if_not_exists(self, mock_bsc_class):
        """If container doesn't exist, it should be created."""
        mock_blob, mock_container, mock_service = _mock_blob_infra()
        mock_bsc_class.from_connection_string.return_value = mock_service
        mock_container.get_container_properties.side_effect = Exception("ContainerNotFound")

        save_state("fake-connection-string", {"uid": {"google_id": "g-1", "sequence": 0, "last_modified": ""}})

        mock_container.create_container.assert_called_once()
