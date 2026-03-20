import logging
import os

import azure.functions as func

from sync.ics_parser import fetch_and_parse
from sync.diff import compute_diff
from sync.google_calendar import create_event, update_event, delete_event
from sync.state import load_state, save_state

app = func.FunctionApp()

logger = logging.getLogger(__name__)


@app.timer_trigger(
    schedule="0 */3 * * * *",  # Every 3 minutes
    arg_name="timer",
    run_on_startup=False,
)
def calendar_sync(timer: func.TimerRequest) -> None:
    """Main sync function: fetch ICS → diff → sync to Google Calendar → save state."""
    if timer.past_due:
        logger.warning("Timer is past due, running anyway")

    ics_url = os.environ["ICS_URL"]
    google_credentials = os.environ["GOOGLE_CREDENTIALS_JSON"]
    google_calendar_id = os.environ["GOOGLE_CALENDAR_ID"]
    storage_connection = os.environ["AzureWebJobsStorage"]

    # 1. Fetch and parse ICS
    logger.info("Fetching ICS from %s", ics_url)
    current_events = fetch_and_parse(ics_url)

    # 2. Load saved state
    state = load_state(storage_connection)

    # 3. Compute diff
    diff = compute_diff(current_events, state)

    if not diff.to_create and not diff.to_update and not diff.to_delete:
        logger.info("No changes detected, skipping sync")
        return

    # 4. Apply changes to Google Calendar
    for event in diff.to_create:
        google_id = create_event(google_credentials, google_calendar_id, event)
        state[event.uid] = {
            "google_id": google_id,
            "sequence": event.sequence,
            "last_modified": event.last_modified,
        }

    for event, google_id in diff.to_update:
        update_event(google_credentials, google_calendar_id, google_id, event)
        state[event.uid] = {
            "google_id": google_id,
            "sequence": event.sequence,
            "last_modified": event.last_modified,
        }

    for google_id in diff.to_delete:
        delete_event(google_credentials, google_calendar_id, google_id)

    # Remove deleted UIDs from state
    deleted_uids = [
        uid for uid, s in state.items()
        if s["google_id"] in diff.to_delete
    ]
    for uid in deleted_uids:
        del state[uid]

    # 5. Save updated state
    save_state(storage_connection, state)

    logger.info(
        "Sync complete: %d created, %d updated, %d deleted",
        len(diff.to_create),
        len(diff.to_update),
        len(diff.to_delete),
    )
