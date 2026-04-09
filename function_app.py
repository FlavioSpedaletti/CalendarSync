import logging
import os

import azure.functions as func

from sync.ics_parser import fetch_and_parse
from sync.diff import compute_diff
from sync.google_calendar import create_event, update_event, delete_event
from sync.state import load_state, save_state

app = func.FunctionApp()

logger = logging.getLogger(__name__)

RUN_ON_STARTUP = os.environ.get("RUN_ON_STARTUP", "false").lower() == "true"

@app.timer_trigger(
    schedule="0 */3 * * * *",  # Every 3 minutes
    arg_name="timer",
    run_on_startup=RUN_ON_STARTUP,
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
        logger.info("✅ Nenhuma alteração detectada, sync ignorado")
        return

    # 4. Apply changes to Google Calendar
    try:
        for event in diff.to_create:
            google_id = create_event(google_credentials, google_calendar_id, event)
            state[event.uid] = {
                "google_id": google_id,
                "sequence": event.sequence,
                "dtstart": event.dtstart.isoformat(),
                "dtend": event.dtend.isoformat(),
                "summary": event.summary,
                "rrule": event.rrule,
            }

        for event, google_id in diff.to_update:
            update_event(google_credentials, google_calendar_id, google_id, event)
            state[event.uid] = {
                "google_id": google_id,
                "sequence": event.sequence,
                "dtstart": event.dtstart.isoformat(),
                "dtend": event.dtend.isoformat(),
                "summary": event.summary,
                "rrule": event.rrule,
            }

        for google_id, summary in diff.to_delete:
            delete_event(google_credentials, google_calendar_id, google_id)
    except Exception:
        logger.exception("Erro ao aplicar alterações no Google Calendar")
        raise

    # Remove deleted UIDs from state
    deleted_google_ids = {gid for gid, _ in diff.to_delete}
    deleted_uids = [
        uid for uid, s in state.items()
        if s["google_id"] in deleted_google_ids
    ]
    for uid in deleted_uids:
        del state[uid]

    # Remove forgotten past events from state (they stay in Google Calendar)
    for uid in getattr(diff, "to_forget", []):
        if uid in state:
            del state[uid]

    # 5. Save updated state
    save_state(storage_connection, state)

    # 6. Detailed summary log
    n_create = len(diff.to_create)
    n_update = len(diff.to_update)
    n_delete = len(diff.to_delete)

    logger.info("➕ %d evento(s) criado(s)%s",
                n_create,
                ":" if n_create else "")
    for event in diff.to_create:
        logger.info("   • %s", event.summary)

    logger.info("🔄 %d evento(s) atualizado(s)%s",
                n_update,
                ":" if n_update else "")
    for event, _ in diff.to_update:
        logger.info("   • %s", event.summary)

    logger.info("🗑️  %d evento(s) excluído(s)%s",
                n_delete,
                ":" if n_delete else "")
    for _, summary in diff.to_delete:
        logger.info("   • %s", summary)
