import logging
from dataclasses import dataclass

from sync.ics_parser import CalendarEvent

logger = logging.getLogger(__name__)


@dataclass
class SyncDiff:
    to_create: list[CalendarEvent]
    to_update: list[tuple[CalendarEvent, str]]  # (event, google_event_id)
    to_delete: list[str]  # google_event_ids


def compute_diff(
    current_events: dict[str, CalendarEvent],
    saved_state: dict,
) -> SyncDiff:
    """Compare current ICS events with saved state to determine sync actions.

    saved_state format:
      { "outlook_uid": { "google_id": "...", "sequence": N, "last_modified": "..." } }
    """
    to_create: list[CalendarEvent] = []
    to_update: list[tuple[CalendarEvent, str]] = []
    to_delete: list[str] = []

    # New and updated events
    for uid, event in current_events.items():
        if uid not in saved_state:
            to_create.append(event)
        else:
            state = saved_state[uid]
            if (
                event.sequence != state.get("sequence")
                or event.last_modified != state.get("last_modified")
            ):
                to_update.append((event, state["google_id"]))

    # Deleted events
    for uid, state in saved_state.items():
        if uid not in current_events:
            to_delete.append(state["google_id"])

    logger.info(
        "Diff: %d new, %d updated, %d deleted",
        len(to_create),
        len(to_update),
        len(to_delete),
    )
    return SyncDiff(
        to_create=to_create,
        to_update=to_update,
        to_delete=to_delete,
    )
