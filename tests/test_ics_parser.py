"""Tests for sync.ics_parser — ICS fetching, parsing, and future-event filtering."""

from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from sync.ics_parser import fetch_and_parse, _is_future_event, CalendarEvent
from tests.conftest import (
    make_ics_calendar,
    make_vevent,
    BRT_OFFSET,
)


# ---------------------------------------------------------------------------
# _is_future_event — timezone-aware, naive, and all-day date handling
# ---------------------------------------------------------------------------


class TestIsFutureEvent:
    def test_future_aware_datetime_returns_true(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert _is_future_event(future) is True

    def test_past_aware_datetime_returns_false(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert _is_future_event(past) is False

    def test_future_naive_datetime_returns_true(self):
        """Naive datetimes should be treated as UTC."""
        future = datetime.utcnow() + timedelta(hours=1)
        assert _is_future_event(future) is True

    def test_past_naive_datetime_returns_false(self):
        past = datetime.utcnow() - timedelta(hours=1)
        assert _is_future_event(past) is False

    def test_future_brt_datetime_returns_true(self):
        """BRT (UTC-3) aware datetime in the future."""
        future = datetime.now(BRT_OFFSET) + timedelta(hours=1)
        assert _is_future_event(future) is True

    def test_past_brt_datetime_returns_false(self):
        past = datetime.now(BRT_OFFSET) - timedelta(hours=1)
        assert _is_future_event(past) is False

    def test_future_date_all_day_returns_true(self):
        future_date = date.today() + timedelta(days=1)
        assert _is_future_event(future_date) is True

    def test_past_date_all_day_returns_false(self):
        past_date = date.today() - timedelta(days=2)
        assert _is_future_event(past_date) is False

    def test_today_date_all_day_returns_true(self):
        """An all-day event ending today should still be considered current."""
        assert _is_future_event(date.today()) is True

    def test_now_exactly_returns_true(self):
        """An event ending right now (>=) should be kept."""
        now = datetime.now(timezone.utc)
        assert _is_future_event(now) is True


# ---------------------------------------------------------------------------
# fetch_and_parse — full ICS parsing with mocked HTTP
# ---------------------------------------------------------------------------


def _mock_response(ics_content: str) -> MagicMock:
    resp = MagicMock()
    resp.content = ics_content.encode("utf-8")
    resp.raise_for_status = MagicMock()
    return resp


class TestFetchAndParse:
    def test_parses_future_event_with_brt_timezone(self):
        """A future event with TZID=E. South America Standard Time is parsed correctly."""
        now_brt = datetime.now(BRT_OFFSET)
        start = now_brt + timedelta(hours=2)
        end = start + timedelta(minutes=30)

        ics = make_ics_calendar(
            make_vevent(
                uid="uid-future-001",
                summary="Reunião Futura",
                dtstart=start,
                dtend=end,
                sequence=3,
            )
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 1
        assert "uid-future-001" in events
        event = events["uid-future-001"]
        assert event.summary == "Reunião Futura"
        assert event.sequence == 3
        assert event.all_day is False

    def test_filters_out_past_events(self):
        """Past events should be excluded from results."""
        now_brt = datetime.now(BRT_OFFSET)
        past_start = now_brt - timedelta(days=5)
        past_end = past_start + timedelta(minutes=30)
        future_start = now_brt + timedelta(hours=1)
        future_end = future_start + timedelta(minutes=30)

        ics = make_ics_calendar(
            make_vevent(uid="uid-past", summary="Evento Passado", dtstart=past_start, dtend=past_end),
            make_vevent(uid="uid-future", summary="Evento Futuro", dtstart=future_start, dtend=future_end),
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 1
        assert "uid-future" in events
        assert "uid-past" not in events

    def test_keeps_in_progress_event(self):
        """An event that started in the past but ends in the future should be kept."""
        now_brt = datetime.now(BRT_OFFSET)
        start = now_brt - timedelta(minutes=15)
        end = now_brt + timedelta(minutes=15)

        ics = make_ics_calendar(
            make_vevent(uid="uid-inprogress", summary="Em Andamento", dtstart=start, dtend=end)
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert "uid-inprogress" in events

    def test_parses_all_day_future_event(self):
        """An all-day event in the future should be parsed with all_day=True."""
        now_brt = datetime.now(BRT_OFFSET)
        future_day = now_brt + timedelta(days=3)
        next_day = future_day + timedelta(days=1)

        ics = make_ics_calendar(
            make_vevent(
                uid="uid-allday",
                summary="Feriado",
                dtstart=future_day,
                dtend=next_day,
                all_day=True,
            )
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 1
        assert events["uid-allday"].all_day is True

    def test_filters_out_all_day_past_event(self):
        """An all-day event entirely in the past should be excluded."""
        now_brt = datetime.now(BRT_OFFSET)
        past_day = now_brt - timedelta(days=10)
        next_day = past_day + timedelta(days=1)

        ics = make_ics_calendar(
            make_vevent(uid="uid-allday-past", summary="Feriado Antigo", dtstart=past_day, dtend=next_day, all_day=True)
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 0

    def test_parses_multiple_future_events(self):
        """Multiple future events are all included."""
        now_brt = datetime.now(BRT_OFFSET)
        vevents = []
        for i in range(5):
            start = now_brt + timedelta(hours=i + 1)
            end = start + timedelta(minutes=30)
            vevents.append(
                make_vevent(uid=f"uid-multi-{i}", summary=f"Evento {i}", dtstart=start, dtend=end)
            )

        ics = make_ics_calendar(*vevents)

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 5

    def test_event_without_uid_is_skipped(self):
        """Events missing UID should be silently skipped."""
        now_brt = datetime.now(BRT_OFFSET)
        start = now_brt + timedelta(hours=1)
        end = start + timedelta(minutes=30)

        # Manually craft a VEVENT without UID
        vevent = (
            "BEGIN:VEVENT\n"
            "DESCRIPTION:\\n\n"
            f"SUMMARY:Sem UID\n"
            f"DTSTART;TZID=E. South America Standard Time:{start.strftime('%Y%m%dT%H%M%S')}\n"
            f"DTEND;TZID=E. South America Standard Time:{end.strftime('%Y%m%dT%H%M%S')}\n"
            "SEQUENCE:0\n"
            "END:VEVENT"
        )

        ics = make_ics_calendar(vevent)

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 0

    def test_event_without_dtstart_is_skipped(self):
        """Events missing DTSTART should be silently skipped."""
        vevent = (
            "BEGIN:VEVENT\n"
            "UID:uid-no-dtstart\n"
            "SUMMARY:Sem Data\n"
            "SEQUENCE:0\n"
            "END:VEVENT"
        )

        ics = make_ics_calendar(vevent)

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 0

    def test_event_without_summary_gets_default_title(self):
        """Events without SUMMARY get the default '(Sem título)' label."""
        now_brt = datetime.now(BRT_OFFSET)
        start = now_brt + timedelta(hours=1)
        end = start + timedelta(minutes=30)

        # Manually craft a VEVENT without SUMMARY
        vevent = (
            "BEGIN:VEVENT\n"
            "UID:uid-no-summary\n"
            f"DTSTART;TZID=E. South America Standard Time:{start.strftime('%Y%m%dT%H%M%S')}\n"
            f"DTEND;TZID=E. South America Standard Time:{end.strftime('%Y%m%dT%H%M%S')}\n"
            "SEQUENCE:0\n"
            "END:VEVENT"
        )

        ics = make_ics_calendar(vevent)

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert events["uid-no-summary"].summary == "(Sem título)"

    def test_last_modified_is_parsed(self):
        """LAST-MODIFIED field should be captured as ISO string."""
        now_brt = datetime.now(BRT_OFFSET)
        start = now_brt + timedelta(hours=1)
        end = start + timedelta(minutes=30)
        modified = datetime(2026, 3, 18, 14, 44, 27, tzinfo=timezone.utc)

        ics = make_ics_calendar(
            make_vevent(
                uid="uid-modified",
                summary="Com Last-Modified",
                dtstart=start,
                dtend=end,
                last_modified=modified,
            )
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert events["uid-modified"].last_modified != ""

    def test_http_error_raises_exception(self):
        """HTTP errors should propagate as exceptions."""
        with patch("sync.ics_parser.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = Exception("HTTP 500")
            with pytest.raises(Exception, match="HTTP 500"):
                fetch_and_parse("http://fake.url/cal.ics")

    def test_duplicate_uid_last_one_wins(self):
        """If the ICS has duplicate UIDs (e.g. RECURRENCE-ID overrides), the last one wins."""
        now_brt = datetime.now(BRT_OFFSET)
        start1 = now_brt + timedelta(hours=1)
        end1 = start1 + timedelta(minutes=30)
        start2 = now_brt + timedelta(hours=3)
        end2 = start2 + timedelta(minutes=30)

        ics = make_ics_calendar(
            make_vevent(uid="uid-dup", summary="Original", dtstart=start1, dtend=end1, sequence=0),
            make_vevent(uid="uid-dup", summary="Override", dtstart=start2, dtend=end2, sequence=1),
        )

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 1
        assert events["uid-dup"].summary == "Override"
        assert events["uid-dup"].sequence == 1

    def test_realistic_outlook_structure_with_mixed_past_future(self):
        """Simulates a real Outlook ICS with a mix of past and future events."""
        now_brt = datetime.now(BRT_OFFSET)

        vevents = [
            # Past events (should be filtered)
            make_vevent(uid="uid-daily-past", summary="[Daily] E-Commerce", dtstart=now_brt - timedelta(days=30), dtend=now_brt - timedelta(days=30) + timedelta(minutes=30), sequence=7),
            make_vevent(uid="uid-gmud", summary="hj tem GMUD", dtstart=now_brt - timedelta(days=28), dtend=now_brt - timedelta(days=28) + timedelta(minutes=30)),
            make_vevent(uid="uid-pdi", summary="pdi deo", dtstart=now_brt - timedelta(days=27), dtend=now_brt - timedelta(days=27) + timedelta(minutes=30)),
            # Future events (should be kept)
            make_vevent(uid="uid-1on1-rafael", summary="1:1 Rafael/Flavio", dtstart=now_brt + timedelta(days=1), dtend=now_brt + timedelta(days=1) + timedelta(minutes=30)),
            make_vevent(uid="uid-1on1-marcelo", summary="1:1 Marcelo/Flavio", dtstart=now_brt + timedelta(days=5), dtend=now_brt + timedelta(days=5) + timedelta(minutes=30)),
            make_vevent(uid="uid-review", summary="Review_Planning - E-Commerce", dtstart=now_brt + timedelta(days=3), dtend=now_brt + timedelta(days=3) + timedelta(hours=1, minutes=30), sequence=7),
        ]

        ics = make_ics_calendar(*vevents)

        with patch("sync.ics_parser.requests.get", return_value=_mock_response(ics)):
            events = fetch_and_parse("http://fake.url/cal.ics")

        assert len(events) == 3
        assert "uid-1on1-rafael" in events
        assert "uid-1on1-marcelo" in events
        assert "uid-review" in events
        # Past ones are gone
        assert "uid-daily-past" not in events
        assert "uid-gmud" not in events
        assert "uid-pdi" not in events
