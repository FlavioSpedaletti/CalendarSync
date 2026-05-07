import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sync.ics_parser import CalendarEvent

logger = logging.getLogger(__name__)


@dataclass
class SyncDiff:
    to_create: list[CalendarEvent]
    to_update: list[tuple[CalendarEvent, str]]  # (event, google_event_id)
    to_delete: list[tuple[str, str]]  # (google_event_id, summary)
    to_forget: list[str] = field(default_factory=list)  # uids to remove from state only

def _is_past_event(dtend_iso: str) -> bool:
    try:
        dtend = datetime.fromisoformat(dtend_iso)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=timezone.utc)
        return dtend < datetime.now(timezone.utc)
    except Exception:
        return False


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
    to_forget: list[str] = []

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
                or event.rrule != state.get("rrule")
            ):
                to_update.append((event, state["google_id"]))

    # Deleted events (carry summary for logging)
    for uid, state in saved_state.items():
        if uid not in current_events:
            summary = state.get("summary", "(sem título)")
            dtend_iso = state.get("dtend", "")
            rrule = state.get("rrule")

            # Eventos recorrentes sem UNTIL (infinitos) nunca devem ser deletados
            # apenas por sumirem temporariamente do feed ICS — o Outlook às vezes
            # para de incluí-los na janela de tempo do feed sem que sejam cancelados.
            if rrule and "UNTIL" not in rrule and "COUNT" not in rrule:
                logger.warning(
                    "⚠️  Evento recorrente '%s' sumiu do ICS mas tem RRULE sem fim — "
                    "ignorando deleção para preservar no Google Calendar.",
                    summary,
                )
                to_forget.append(uid)
            # Se o evento já passou e sumiu do ICS, não apagamos do Google
            elif _is_past_event(dtend_iso):
                to_forget.append(uid)
            else:
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
        to_forget=to_forget,
    )
