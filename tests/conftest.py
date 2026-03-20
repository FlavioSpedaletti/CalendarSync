"""Shared fixtures and helpers for CalendarSync tests.

Generates ICS content with dynamic dates so tests always have future events,
based on the real Outlook ICS structure from the reachcalendar.ics files.
"""

from datetime import datetime, date, timedelta, timezone
from textwrap import dedent

from sync.ics_parser import CalendarEvent

# Timezone matching Outlook's "E. South America Standard Time" (UTC-3, no DST)
BRT_OFFSET = timezone(timedelta(hours=-3))


def _fmt_dt(dt: datetime) -> str:
    """Format datetime as ICS TZID value: 20260318T093000"""
    return dt.strftime("%Y%m%dT%H%M%S")


def _fmt_date(d: date) -> str:
    """Format date as ICS all-day value: 20260318"""
    return d.strftime("%Y%m%d")


def _fmt_utc(dt: datetime) -> str:
    """Format datetime as ICS UTC value: 20260318T123000Z"""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def make_ics_calendar(*vevents: str) -> str:
    """Wrap VEVENT blocks in a valid VCALENDAR with the Outlook timezone."""
    header = dedent("""\
        BEGIN:VCALENDAR
        METHOD:PUBLISH
        PRODID:Microsoft Exchange Server 2010
        VERSION:2.0
        X-WR-CALNAME:Calendar
        BEGIN:VTIMEZONE
        TZID:E. South America Standard Time
        BEGIN:STANDARD
        DTSTART:16010101T000000
        TZOFFSETFROM:-0300
        TZOFFSETTO:-0300
        END:STANDARD
        END:VTIMEZONE
    """)
    footer = "END:VCALENDAR\n"
    return header + "\n".join(vevents) + "\n" + footer


def make_vevent(
    uid: str,
    summary: str,
    dtstart: datetime,
    dtend: datetime,
    sequence: int = 0,
    all_day: bool = False,
    with_rrule: str | None = None,
    recurrence_id: str | None = None,
    last_modified: datetime | None = None,
) -> str:
    """Generate a VEVENT block mimicking real Outlook ICS structure."""
    lines = ["BEGIN:VEVENT", "DESCRIPTION:\\n"]

    if with_rrule:
        lines.append(f"RRULE:{with_rrule}")

    lines.append(f"UID:{uid}")

    if recurrence_id:
        lines.append(f"RECURRENCE-ID;TZID=E. South America Standard Time:{recurrence_id}")

    lines.append(f"SUMMARY:{summary}")

    if all_day:
        lines.append(f"DTSTART;VALUE=DATE:{_fmt_date(dtstart.date() if isinstance(dtstart, datetime) else dtstart)}")
        lines.append(f"DTEND;VALUE=DATE:{_fmt_date(dtend.date() if isinstance(dtend, datetime) else dtend)}")
    else:
        lines.append(f"DTSTART;TZID=E. South America Standard Time:{_fmt_dt(dtstart)}")
        lines.append(f"DTEND;TZID=E. South America Standard Time:{_fmt_dt(dtend)}")

    lines.append("CLASS:PUBLIC")
    lines.append("PRIORITY:5")
    lines.append(f"DTSTAMP:{_fmt_utc(datetime.now(timezone.utc))}")
    lines.append("TRANSP:OPAQUE")
    lines.append("STATUS:CONFIRMED")
    lines.append(f"SEQUENCE:{sequence}")
    lines.append("LOCATION:")
    lines.append(f"X-MICROSOFT-CDO-APPT-SEQUENCE:{sequence}")
    lines.append("X-MICROSOFT-CDO-BUSYSTATUS:BUSY")
    lines.append("X-MICROSOFT-CDO-INTENDEDSTATUS:BUSY")
    lines.append(f"X-MICROSOFT-CDO-ALLDAYEVENT:{'TRUE' if all_day else 'FALSE'}")
    lines.append("X-MICROSOFT-CDO-IMPORTANCE:1")
    lines.append("X-MICROSOFT-CDO-INSTTYPE:0")
    lines.append("X-MICROSOFT-DONOTFORWARDMEETING:FALSE")
    lines.append("X-MICROSOFT-DISALLOW-COUNTER:FALSE")

    if last_modified:
        lines.append(f"LAST-MODIFIED:{_fmt_utc(last_modified)}")

    lines.append("END:VEVENT")
    return "\n".join(lines)


def make_future_event(
    uid: str = "test-uid-001",
    summary: str = "Reunião de Teste",
    hours_from_now: int = 2,
    duration_minutes: int = 30,
    sequence: int = 0,
    all_day: bool = False,
    last_modified: datetime | None = None,
) -> CalendarEvent:
    """Create a CalendarEvent dataclass with a future datetime."""
    now = datetime.now(BRT_OFFSET)
    start = now + timedelta(hours=hours_from_now)
    end = start + timedelta(minutes=duration_minutes)

    if all_day:
        return CalendarEvent(
            uid=uid,
            summary=summary,
            dtstart=start.date(),
            dtend=end.date(),
            sequence=sequence,
            last_modified=last_modified.isoformat() if last_modified else "",
            all_day=True,
        )

    return CalendarEvent(
        uid=uid,
        summary=summary,
        dtstart=start,
        dtend=end,
        sequence=sequence,
        last_modified=last_modified.isoformat() if last_modified else "",
        all_day=False,
    )
