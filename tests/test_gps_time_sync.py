from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import gps_time_syc_vk172.gps_time_sync as gps_time_sync
from gps_time_syc_vk172.gps_time_sync import (
    GPSStatus,
    parse_gga_sentence,
    parse_gsa_sentence,
    parse_gsv_sentence,
    parse_rmc_sentence,
    set_system_time,
)


def test_parse_rmc_sentence_returns_datetime_for_valid_sentence():
    sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    result = parse_rmc_sentence(sentence)
    assert result is not None
    assert result.status == "A"
    assert result.timestamp == datetime(1994, 3, 23, 12, 35, 19, tzinfo=timezone.utc)


def test_parse_rmc_sentence_returns_status_for_invalid_fix():
    sentence = "$GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*7D"
    result = parse_rmc_sentence(sentence)
    assert result is not None
    assert result.status == "V"
    assert result.timestamp is None


def test_parse_rmc_sentence_returns_none_for_bad_checksum():
    sentence = "$GPRMC,092751,A,5321.6802,N,00630.3372,W,0.06,31.66,280511,,,N*00"
    assert parse_rmc_sentence(sentence) is None


def test_parse_gga_sentence_extracts_fix_information():
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    result = parse_gga_sentence(sentence)
    assert result is not None
    assert result.fix_quality == 1
    assert result.satellites_in_use == 8
    assert result.hdop == pytest.approx(0.9)


def test_parse_gsa_sentence_extracts_satellite_usage():
    sentence = "$GPGSA,A,3,04,05,09,12,24,30,,,,,,,2.5,1.3,2.1*3A"
    result = parse_gsa_sentence(sentence)
    assert result is not None
    assert result.fix_mode == 3
    assert result.satellites_in_use == 6
    assert result.pdop == pytest.approx(2.5)
    assert result.hdop == pytest.approx(1.3)
    assert result.vdop == pytest.approx(2.1)


def test_parse_gsv_sentence_extracts_satellites_in_view():
    sentence = "$GPGSV,2,1,08,01,40,083,41,02,17,308,43,03,23,123,42,04,10,053,30*75"
    result = parse_gsv_sentence(sentence)
    assert result is not None
    assert result.satellites_in_view == 8


def test_gps_status_summary_contains_key_information():
    status = GPSStatus(
        fix_status="A",
        fix_quality=1,
        fix_mode=3,
        satellites_in_use=10,
        satellites_in_view=12,
        hdop=0.8,
        pdop=1.5,
        vdop=1.2,
    )
    summary = status.summary_lines()
    assert "Fix status: Active" in summary[0]
    assert any("Satellites in use: 10" == line for line in summary)
    assert any("Satellites in view: 12" == line for line in summary)
    assert any("HDOP: 0.80" == line for line in summary)
    assert any("PDOP: 1.50" == line for line in summary)
    assert any("VDOP: 1.20" == line for line in summary)


def test_set_system_time_uses_clock_settime(monkeypatch):
    timestamps = []

    def fake_clock_settime(clock_id, timestamp):
        timestamps.append(timestamp)

    monkeypatch.setattr("time.clock_settime", fake_clock_settime, raising=False)
    set_system_time(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert pytest.approx(timestamps[0], rel=0, abs=1e-6) == 1704164645.0


def test_set_system_time_raises_for_permission_issue(monkeypatch):
    def fake_clock_settime(clock_id, timestamp):
        raise PermissionError("no permission")

    monkeypatch.setattr("time.clock_settime", fake_clock_settime, raising=False)

    with pytest.raises(PermissionError):
        set_system_time(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))


def test_set_system_time_falls_back_to_date_command(monkeypatch):
    def fake_clock_settime(clock_id, timestamp):
        raise AttributeError("not available")

    monkeypatch.setattr("time.clock_settime", fake_clock_settime, raising=False)

    calls = {}

    def fake_run(args, check, capture_output, text):
        calls["args"] = args
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("subprocess.run", fake_run)

    set_system_time(datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    assert calls["args"] == ["date", "-u", "-s", "2023-12-31 23:59:59"]


def test_acquire_gps_time_returns_immediately_when_details_not_required(monkeypatch):
    sentences = iter(
        [
            b"$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n",
        ]
    )

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            self._sentences = sentences

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def readline(self):
            return next(self._sentences, b"")

        def reset_input_buffer(self):
            pass

    monkeypatch.setattr(gps_time_sync.serial, "Serial", FakeSerial)
    gps_time, status = gps_time_sync.acquire_gps_time(
        port="/dev/ttyFAKE",
        timeout=1,
        warmup=0,
        require_detailed_status=False,
    )
    assert gps_time == datetime(1994, 3, 23, 12, 35, 19, tzinfo=timezone.utc)
    assert status.fix_status == "A"


def test_acquire_gps_time_waits_for_status_when_requested(monkeypatch):
    sentences = iter(
        [
            b"$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A\r\n",
            b"$GPGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*4D\r\n",
        ]
    )

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            self._sentences = sentences

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def readline(self):
            return next(self._sentences, b"")

        def reset_input_buffer(self):
            pass

    monkeypatch.setattr(gps_time_sync.serial, "Serial", FakeSerial)

    gps_time, status = gps_time_sync.acquire_gps_time(
        port="/dev/ttyFAKE",
        timeout=1,
        warmup=0,
        require_detailed_status=True,
    )

    assert gps_time == datetime(1994, 3, 23, 12, 35, 19, tzinfo=timezone.utc)
    assert status.satellites_in_use == 8
    assert status.has_detail_metrics()


def test_cli_status_prints_times(monkeypatch, capsys):
    gps_dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    fake_status = GPSStatus(fix_status="A")

    def fake_acquire_gps_time(**kwargs):
        return gps_dt, fake_status

    monkeypatch.setattr(gps_time_sync, "acquire_gps_time", fake_acquire_gps_time)
    monkeypatch.setattr(gps_time_sync, "set_system_time", lambda dt: None)

    exit_code = gps_time_sync.cli(["--status", "--port", "/dev/ttyFAKE"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "GPS UTC time: 2024-01-02T03:04:05+00:00" in captured.out
    expected_local = gps_dt.astimezone().isoformat()
    assert f"Local time: {expected_local}" in captured.out
