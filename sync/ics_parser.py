import logging
from dataclasses import dataclass
from datetime import datetime, date, timezone

import requests
from icalendar import Calendar

logger = logging.getLogger(__name__)


def _is_future_event(dtend: datetime | date) -> bool:
    """Check if an event ends in the future, handling timezone-aware and naive datetimes."""
    now = datetime.now(timezone.utc)

    if isinstance(dtend, datetime):
        # Make aware if naive (assume UTC)
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=timezone.utc)
        return dtend >= now
    else:
        # All-day event: compare date only (event ends after today in UTC)
        return dtend >= now.date()


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    dtstart: datetime | date
    dtend: datetime | date
    sequence: int
    last_modified: str
    all_day: bool
    rrule: str | None = None


def fetch_and_parse(ics_url: str) -> dict[str, CalendarEvent]:
    """Fetch an .ics file from a URL and parse all VEVENT components."""
    response = requests.get(ics_url, timeout=30)
    response.raise_for_status()

    cal = Calendar.from_ical(response.content)
    events: dict[str, CalendarEvent] = {}

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID", ""))
        if not uid:
            continue

        summary = str(component.get("SUMMARY", "(Sem título)"))
        dtstart_prop = component.get("DTSTART")
        dtend_prop = component.get("DTEND")

        if not dtstart_prop:
            continue

        dtstart = dtstart_prop.dt
        dtend = dtend_prop.dt if dtend_prop else dtstart
        all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

        rrule_prop = component.get("RRULE")
        rrule_str = None
        has_future_recurrence = False

        if rrule_prop:
            rrule_str = rrule_prop.to_ical().decode("utf-8")
            until_values = rrule_prop.get("UNTIL")
            if until_values:
                 until_dt = until_values[0] if isinstance(until_values, list) else until_values
                 has_future_recurrence = _is_future_event(until_dt)
            else:
                 has_future_recurrence = True

        # Skip past events (use dtend so in-progress events are kept),
        # unless it has a recurrence targeting future dates.
        if not _is_future_event(dtend) and not has_future_recurrence:
            continue

        sequence = int(component.get("SEQUENCE", 0))
        last_modified_prop = component.get("LAST-MODIFIED")
        last_modified = (
            last_modified_prop.dt.isoformat() if last_modified_prop else ""
        )

        events[uid] = CalendarEvent(
            uid=uid,
            summary=summary,
            dtstart=dtstart,
            dtend=dtend,
            sequence=sequence,
            last_modified=last_modified,
            all_day=all_day,
            rrule=rrule_str,
        )

    logger.info("Parsed %d events from ICS", len(events))
    return events
