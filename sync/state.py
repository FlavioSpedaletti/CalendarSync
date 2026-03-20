import json
import logging

from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

CONTAINER_NAME = "calendar-sync"
BLOB_NAME = "state.json"


def _get_blob_client(connection_string: str):
    blob_service = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service.get_container_client(CONTAINER_NAME)
    # Ensure container exists
    try:
        container_client.get_container_properties()
    except Exception:
        container_client.create_container()
    return container_client.get_blob_client(BLOB_NAME)


def load_state(connection_string: str) -> dict:
    """Load the sync state from Azure Blob Storage.

    Returns dict: { "outlook_uid": { "google_id": "...", "sequence": N, "last_modified": "..." } }
    """
    blob_client = _get_blob_client(connection_string)
    try:
        data = blob_client.download_blob().readall()
        state = json.loads(data)
        logger.info("Loaded state with %d entries", len(state))
        return state
    except Exception:
        logger.info("No existing state found, starting fresh")
        return {}


def save_state(connection_string: str, state: dict) -> None:
    """Save the sync state to Azure Blob Storage."""
    blob_client = _get_blob_client(connection_string)
    blob_client.upload_blob(
        json.dumps(state, indent=2),
        overwrite=True,
    )
    logger.info("Saved state with %d entries", len(state))
