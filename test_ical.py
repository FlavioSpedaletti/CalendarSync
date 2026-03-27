from icalendar import Calendar
with open('c:/Projetos/CalendarSync/exemplos ics/reachcalendar (2).ics', 'rb') as f:
    cal = Calendar.from_ical(f.read())

for component in cal.walk():
    if component.name == "VEVENT":
        rrule = component.get('RRULE')
        if rrule:
            print("Summary:", component.get("SUMMARY"))
            print("RRULE raw:", rrule)
            print("RRULE to_ical:", rrule.to_ical().decode('utf-8'))
            break
