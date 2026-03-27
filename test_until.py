from icalendar import Calendar
from src_is_future_event import _is_future_event

def _is_future_event(dtend) -> bool:
    from datetime import datetime, timezone, date
    now = datetime.now(timezone.utc)
    if isinstance(dtend, datetime):
        if dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=timezone.utc)
        return dtend >= now
    else:
        return dtend >= now.date()

with open('c:/Projetos/CalendarSync/exemplos ics/reachcalendar (2).ics', 'rb') as f:
    cal = Calendar.from_ical(f.read())

for component in cal.walk():
    if component.name == "VEVENT":
        rrule_prop = component.get("RRULE")
        if rrule_prop:
            print("Summary:", component.get("SUMMARY"))
            until_values = rrule_prop.get("UNTIL")
            if until_values:
                 until_dt = until_values[0]
                 print("Type UNTIL:", type(until_dt), until_dt)
                 print("Future?", _is_future_event(until_dt))
            else:
                 print("No UNTIL")
            break
