"""Tests for sync.google_calendar — event body building and title formatting."""

from datetime import datetime, date, timedelta, timezone

from sync.google_calendar import _build_event_body, TITLE_PREFIX
from tests.conftest import make_future_event, BRT_OFFSET


class TestBuildEventBody:
    def test_title_has_bs2_prefix(self):
        """Event summary should be formatted as 'BS2 - {original}'."""
        event = make_future_event(summary="[Daily] E-Commerce")
        body = _build_event_body(event)
        assert body["summary"] == f"{TITLE_PREFIX} - [Daily] E-Commerce"

    def test_timed_event_has_datetime_fields(self):
        """Non-all-day events should use dateTime/timeZone in start/end."""
        event = make_future_event(summary="Reunião", all_day=False)
        body = _build_event_body(event)

        assert "dateTime" in body["start"]
        assert "timeZone" in body["start"]
        assert "dateTime" in body["end"]
        assert "timeZone" in body["end"]
        assert "date" not in body["start"]

    def test_all_day_event_has_date_fields(self):
        """All-day events should use date (not dateTime) in start/end."""
        event = make_future_event(summary="Feriado", all_day=True)
        body = _build_event_body(event)

        assert "date" in body["start"]
        assert "date" in body["end"]
        assert "dateTime" not in body["start"]

    def test_title_with_special_characters(self):
        """Special characters in summary (accents, pipes) should be preserved."""
        event = make_future_event(summary="Café com Estratégia | Edição 28")
        body = _build_event_body(event)
        assert body["summary"] == f"{TITLE_PREFIX} - Café com Estratégia | Edição 28"

    def test_title_with_brackets(self):
        """Brackets in summary (e.g. [Daily]) should be preserved."""
        event = make_future_event(summary="[É HOJE] Workshop de Capacitação GitHub - Online")
        body = _build_event_body(event)
        assert body["summary"] == f"{TITLE_PREFIX} - [É HOJE] Workshop de Capacitação GitHub - Online"

    def test_body_has_only_summary_start_end(self):
        """Event body should only contain summary, start, end — no description or attendees."""
        event = make_future_event(summary="Teste")
        body = _build_event_body(event)

        assert set(body.keys()) == {"summary", "start", "end"}

    def test_timezone_string_in_timed_event(self):
        """The timeZone field should contain the timezone info from dtstart/dtend."""
        event = make_future_event(summary="Teste TZ", all_day=False)
        body = _build_event_body(event)

        # BRT_OFFSET is UTC-03:00
        tz = body["start"]["timeZone"]
        assert tz is not None
        assert tz != ""

    def test_naive_datetime_defaults_to_utc(self):
        """If dtstart has no timezone, timeZone should default to 'UTC'."""
        from sync.ics_parser import CalendarEvent

        now = datetime.utcnow() + timedelta(hours=2)
        event = CalendarEvent(
            uid="uid-naive",
            summary="Naive TZ",
            dtstart=now,
            dtend=now + timedelta(minutes=30),
            sequence=0,
            last_modified="",
            all_day=False,
        )
        body = _build_event_body(event)
        assert body["start"]["timeZone"] == "UTC"
        assert body["end"]["timeZone"] == "UTC"
