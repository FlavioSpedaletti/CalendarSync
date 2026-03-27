import logging
from dataclasses import dataclass

from sync.ics_parser import CalendarEvent

logger = logging.getLogger(__name__)


@dataclass
class SyncDiff:
    to_create: list[CalendarEvent]
    to_update: list[tuple[CalendarEvent, str]]  # (event, google_event_id)
    to_delete: list[tuple[str, str]]  # (google_event_id, summary)


def compute_diff(
    current_events: dict[str, CalendarEvent],
    saved_state: dict,
) -> SyncDiff:
    """Compare current ICS events with saved state to determine sync actions.

    saved_state format:
      { "outlook_uid": { "google_id": "...", "sequence": N,
                         "dtstart": "...", "dtend": "...", "summary": "..." } }
    """
    to_create: list[CalendarEvent] = []
    to_update: list[tuple[CalendarEvent, str]] = []
    to_delete: list[tuple[str, str]] = []

    # New and updated events
    for uid, event in current_events.items():
        if uid not in saved_state:
            to_create.append(event)
        else:
            state = saved_state[uid]
            if (
                event.sequence != state.get("sequence")
                or event.dtstart.isoformat() != state.get("dtstart")
                or event.dtend.isoformat() != state.get("dtend")
                or event.summary != state.get("summary")
            ):
                to_update.append((event, state["google_id"]))

    # Deleted events (carry summary for logging)
    for uid, state in saved_state.items():
        if uid not in current_events:
            summary = state.get("summary", "(sem título)")
            to_delete.append((state["google_id"], summary))

    logger.info(
        "Diff: %d novo(s), %d atualizado(s), %d excluído(s)",
        len(to_create),
        len(to_update),
        len(to_delete),
    )
    return SyncDiff(
        to_create=to_create,
        to_update=to_update,
        to_delete=to_delete,
    )
