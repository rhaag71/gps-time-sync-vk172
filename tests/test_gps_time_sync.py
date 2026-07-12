import errno
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import gps_time_sync_vk172.gps_time_sync as gps_time_sync
from gps_time_sync_vk172.gps_time_sync import (
    GPSStatus,
    parse_gga_sentence,
    parse_gsa_sentence,
    parse_gsv_sentence,
    parse_rmc_sentence,
    set_system_time,
)


def nmea(body: str) -> str:
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f"${body}*{checksum:02X}"


RMC = nmea("GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W")
GGA = nmea("GPGGA,123520,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,")
GSA = nmea("GPGSA,A,3,04,05,09,12,24,30,31,32,,,,,2.5,1.3,2.1")
GSV_1 = nmea("GPGSV,2,1,08,01,40,083,41,02,17,308,43,03,23,123,42,04,10,053,30")
GSV_2 = nmea("GPGSV,2,2,08,05,67,010,45,06,34,220,40,07,12,180,35,08,05,300,20")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def install_serial(
    monkeypatch,
    lines=(),
    *,
    clock: FakeClock | None = None,
    read_step: float = 0.1,
    open_error: Exception | None = None,
    read_error: Exception | None = None,
):
    encoded = iter(line if isinstance(line, bytes) else f"{line}\r\n".encode() for line in lines)
    instances = []

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            if open_error is not None:
                raise open_error
            self.timeout = kwargs["timeout"]
            self.read_count = 0
            self.reset_count = 0
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def readline(self):
            self.read_count += 1
            if clock is not None:
                clock.now += min(read_step, self.timeout)
            if read_error is not None:
                raise read_error
            return next(encoded, b"")

        def reset_input_buffer(self):
            self.reset_count += 1

    monkeypatch.setattr(gps_time_sync.serial, "Serial", FakeSerial)
    if clock is not None:
        monkeypatch.setattr(gps_time_sync.time, "monotonic", clock.monotonic)
        monkeypatch.setattr(gps_time_sync.time, "sleep", clock.sleep)
    return instances


def test_parse_rmc_sentence_returns_datetime_for_valid_sentence():
    result = parse_rmc_sentence(RMC)
    assert result is not None
    assert result.status == "A"
    assert result.timestamp == datetime(1994, 3, 23, 12, 35, 19, tzinfo=timezone.utc)


def test_parse_rmc_sentence_returns_status_for_invalid_fix():
    result = parse_rmc_sentence(
        nmea("GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W")
    )
    assert result is not None
    assert result.status == "V"
    assert result.timestamp is None


@pytest.mark.parametrize(
    ("time_field", "date_field"),
    [("", "230394"), ("123519", ""), ("250000", "230394"), ("123519", "310299")],
)
def test_parse_rmc_rejects_missing_or_invalid_datetime(time_field, date_field):
    result = parse_rmc_sentence(
        nmea(f"GPRMC,{time_field},A,4807.038,N,01131.000,E,0,0,{date_field},,,")
    )
    assert result is not None
    assert result.timestamp is None


def test_parse_rmc_fractional_seconds():
    result = parse_rmc_sentence(nmea("GNRMC,235959.1234,A,,,,,,,311224,,,"))
    assert result is not None
    assert result.timestamp == datetime(
        2024, 12, 31, 23, 59, 59, 123400, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(("year", "expected"), [("79", 2079), ("80", 1980)])
def test_parse_rmc_year_boundary(year, expected):
    result = parse_rmc_sentence(nmea(f"GPRMC,000000,A,,,,,,,0101{year},,,"))
    assert result is not None
    assert result.timestamp is not None
    assert result.timestamp.year == expected


def test_parse_rmc_rejects_malformed_checksum_text():
    assert parse_rmc_sentence("$GPRMC,123519,A,,,,,,,230394,,,*ZZ") is None


def test_parse_rmc_rejects_invalid_checksum():
    assert parse_rmc_sentence(f"{RMC[:-2]}00") is None


@pytest.mark.parametrize(
    ("parser", "body"),
    [
        (parse_rmc_sentence, "GNRMC,123519,A,,,,,,,230394,,,"),
        (parse_gga_sentence, "GNGGA,123520,,,,,1,08,0.9,,,,,,"),
        (parse_gsa_sentence, "GNGSA,A,3,04,05,09,12,24,30,,,,,,,2.5,1.3,2.1"),
        (parse_gsv_sentence, "GNGSV,1,1,02,01,40,083,41,02,17,308,43"),
    ],
)
def test_alternate_gn_talker_ids(parser, body):
    assert parser(nmea(body)) is not None


def test_parse_gga_sentence_extracts_fix_information():
    result = parse_gga_sentence(GGA)
    assert result is not None
    assert (result.fix_quality, result.satellites_in_use, result.hdop) == (1, 8, 0.9)


def test_parse_gsa_sentence_extracts_satellite_usage():
    result = parse_gsa_sentence(GSA)
    assert result is not None
    assert result.fix_mode == 3
    assert result.satellites_in_use == 8
    assert (result.pdop, result.hdop, result.vdop) == pytest.approx((2.5, 1.3, 2.1))


def test_parse_gsv_sentence_extracts_satellites_in_view():
    result = parse_gsv_sentence(GSV_1)
    assert result is not None
    assert result.satellites_in_view == 8


@pytest.mark.parametrize(
    ("fix_mode", "expected"),
    [
        (None, "Fix mode: Unknown"),
        (1, "Fix mode: No fix"),
        (2, "Fix mode: 2D"),
        (3, "Fix mode: 3D"),
        (9, "Fix mode: Unknown"),
    ],
)
def test_fix_mode_summary(fix_mode, expected):
    lines = GPSStatus(fix_mode=fix_mode).summary_lines()
    assert expected in lines


def test_gps_status_summary_contains_key_information():
    status = GPSStatus(
        fix_status="A", fix_quality=1, fix_mode=3, satellites_in_use=10,
        satellites_in_view=12, hdop=0.8, pdop=1.5, vdop=1.2,
    )
    summary = status.summary_lines()
    assert "Fix status: Active" in summary[0]
    assert "Satellites in use: 10" in summary
    assert "Satellites in view: 12" in summary
    assert "HDOP: 0.80" in summary
    assert "PDOP: 1.50" in summary
    assert "VDOP: 1.20" in summary


def test_status_detail_requires_fix_and_satellite_information():
    assert not GPSStatus(fix_quality=1).has_detail_metrics()
    assert not GPSStatus(satellites_in_view=8).has_detail_metrics()
    assert GPSStatus(fix_quality=1, satellites_in_use=8).has_detail_metrics()


def test_acquire_returns_immediately_when_details_not_requested(monkeypatch):
    clock = FakeClock()
    instances = install_serial(monkeypatch, [RMC], clock=clock)
    gps_time, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=1, warmup=0
    )
    assert gps_time == datetime(1994, 3, 23, 12, 35, 19, tzinfo=timezone.utc)
    assert status.fix_status == "A"
    assert instances[0].read_count == 1


@pytest.mark.parametrize(
    "lines",
    [[RMC, GGA, GSA], [GGA, GSA, RMC], [RMC, GSA, GGA]],
)
def test_status_collection_accepts_realistic_sentence_orderings(monkeypatch, lines):
    clock = FakeClock()
    install_serial(monkeypatch, lines, clock=clock)
    _, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=5, warmup=0, require_detailed_status=True
    )
    assert status.fix_quality == 1
    assert status.fix_mode == 3
    assert status.satellites_in_use == 8


def test_status_collection_accepts_completed_multipart_gsv(monkeypatch):
    clock = FakeClock()
    install_serial(monkeypatch, [RMC, GSV_1, GGA, GSV_2], clock=clock)
    _, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=5, warmup=0, require_detailed_status=True
    )
    assert status.fix_quality == 1
    assert status.satellites_in_view == 8


def test_status_collection_does_not_treat_last_gsv_part_as_complete(monkeypatch):
    clock = FakeClock()
    install_serial(monkeypatch, [RMC, GGA, GSV_2], clock=clock, read_step=0.25)
    _, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=5, warmup=0, require_detailed_status=True,
        status_collection_window=0.75,
    )
    assert status.satellites_in_view == 8
    assert clock.now == pytest.approx(1.0)


def test_status_collection_returns_partial_gga_after_window(monkeypatch):
    clock = FakeClock()
    install_serial(monkeypatch, [RMC, GGA], clock=clock, read_step=0.25)
    _, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=5, warmup=0, require_detailed_status=True,
        status_collection_window=0.5,
    )
    assert status.fix_quality == 1
    assert status.fix_mode is None
    assert clock.now == pytest.approx(0.75)


def test_overall_timeout_caps_status_window(monkeypatch):
    clock = FakeClock()
    install_serial(monkeypatch, [RMC, GGA], clock=clock, read_step=0.1)
    _, status = gps_time_sync.acquire_gps_time(
        "/dev/ttyFAKE", timeout=0.3, warmup=0, require_detailed_status=True,
        status_collection_window=5,
    )
    assert status.fix_quality == 1
    assert clock.now == pytest.approx(0.3)


@pytest.mark.parametrize("position", ["before", "inside", "after"])
def test_non_ascii_serial_data_is_skipped_without_mutation(monkeypatch, position):
    raw = RMC.encode()
    if position == "before":
        malformed = b"\xff" + raw
    elif position == "inside":
        malformed = raw[:10] + b"\xff" + raw[10:]
    else:
        malformed = raw + b"\xff"
    clock = FakeClock()
    instances = install_serial(monkeypatch, [malformed, RMC], clock=clock)
    gps_time, _ = gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=0)
    assert gps_time is not None
    assert instances[0].read_count == 2


def test_positive_warmup_precedes_acquisition_deadline(monkeypatch):
    clock = FakeClock()
    instances = install_serial(monkeypatch, [], clock=clock, read_step=0.5)
    with pytest.raises(TimeoutError):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=2)
    assert clock.sleeps == [2]
    assert clock.now == pytest.approx(3)
    assert instances[0].reset_count == 1


def test_zero_warmup_does_not_sleep_or_reset(monkeypatch):
    clock = FakeClock()
    instances = install_serial(monkeypatch, [], clock=clock, read_step=0.5)
    with pytest.raises(TimeoutError):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=0)
    assert clock.sleeps == []
    assert instances[0].reset_count == 0


def test_zero_timeout_does_not_read(monkeypatch):
    clock = FakeClock()
    instances = install_serial(monkeypatch, [RMC], clock=clock)
    with pytest.raises(TimeoutError):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=0, warmup=0)
    assert instances[0].read_count == 0


@pytest.mark.parametrize(
    "kwargs", [{"timeout": -1}, {"warmup": -1}, {"status_collection_window": -1}]
)
def test_negative_durations_are_rejected_before_open(monkeypatch, kwargs):
    instances = install_serial(monkeypatch, [RMC])
    with pytest.raises(ValueError, match="non-negative"):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", **kwargs)
    assert instances == []


def test_no_valid_fix_before_deadline(monkeypatch):
    clock = FakeClock()
    install_serial(monkeypatch, [GGA], clock=clock, read_step=0.25)
    with pytest.raises(TimeoutError):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=0.5, warmup=0)


def test_serial_open_failure_propagates(monkeypatch):
    install_serial(monkeypatch, open_error=gps_time_sync.serial.SerialException("open"))
    with pytest.raises(gps_time_sync.serial.SerialException, match="open"):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=0)


def test_serial_read_failure_propagates(monkeypatch):
    clock = FakeClock()
    install_serial(
        monkeypatch, clock=clock,
        read_error=gps_time_sync.serial.SerialException("read"),
    )
    with pytest.raises(gps_time_sync.serial.SerialException, match="read"):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=0)


def test_empty_reads_continue_until_timeout(monkeypatch):
    clock = FakeClock()
    instances = install_serial(monkeypatch, [], clock=clock, read_step=0.25)
    with pytest.raises(TimeoutError):
        gps_time_sync.acquire_gps_time("/dev/ttyFAKE", timeout=1, warmup=0)
    assert instances[0].read_count == 4


def install_clock_error(monkeypatch, error):
    def fake_clock_settime(clock_id, timestamp):
        raise error
    monkeypatch.setattr(gps_time_sync.time, "clock_settime", fake_clock_settime, raising=False)


def install_successful_date(monkeypatch):
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stderr="", stdout="")
    monkeypatch.setattr(gps_time_sync.subprocess, "run", fake_run)
    return calls


def test_set_system_time_uses_clock_settime(monkeypatch):
    calls = []
    monkeypatch.setattr(
        gps_time_sync.time, "clock_settime",
        lambda clock_id, timestamp: calls.append((clock_id, timestamp)), raising=False,
    )
    set_system_time(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    assert calls[0][1] == pytest.approx(1704164645.0)


def test_set_system_time_rejects_naive_datetime(monkeypatch):
    calls = []
    monkeypatch.setattr(gps_time_sync.time, "clock_settime", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="timezone-aware"):
        set_system_time(datetime(2024, 1, 2))
    assert calls == []


def test_set_system_time_permission_failure_does_not_fallback(monkeypatch):
    install_clock_error(monkeypatch, PermissionError("denied"))
    monkeypatch.setattr(
        gps_time_sync.subprocess, "run",
        lambda *args, **kwargs: pytest.fail("date fallback must not run"),
    )
    with pytest.raises(PermissionError, match="CAP_SYS_TIME"):
        set_system_time(datetime(2024, 1, 2, tzinfo=timezone.utc))


@pytest.mark.parametrize(
    "error",
    [
        AttributeError("missing"),
        NotImplementedError("unsupported"),
        OSError(errno.ENOSYS, "unsupported"),
        OSError(errno.ENOTSUP, "unsupported"),
    ],
)
def test_set_system_time_supported_failures_use_date(monkeypatch, error):
    install_clock_error(monkeypatch, error)
    calls = install_successful_date(monkeypatch)
    set_system_time(datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
    assert calls == [["date", "-u", "-s", "2023-12-31 23:59:59"]]


def test_set_system_time_unsupported_oserror_propagates(monkeypatch):
    install_clock_error(monkeypatch, OSError(errno.EIO, "I/O failure"))
    with pytest.raises(OSError) as exc_info:
        set_system_time(datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert exc_info.value.errno == errno.EIO


def test_set_system_time_date_failure_has_diagnostic(monkeypatch):
    install_clock_error(monkeypatch, AttributeError("missing"))
    monkeypatch.setattr(
        gps_time_sync.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="date denied", stdout=""),
    )
    with pytest.raises(RuntimeError, match="date denied"):
        set_system_time(datetime(2024, 1, 2, tzinfo=timezone.utc))


def test_set_system_time_missing_date_command_has_diagnostic(monkeypatch):
    install_clock_error(monkeypatch, AttributeError("missing"))
    monkeypatch.setattr(
        gps_time_sync.subprocess, "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("date missing")),
    )
    with pytest.raises(RuntimeError, match="date missing"):
        set_system_time(datetime(2024, 1, 2, tzinfo=timezone.utc))


def fake_acquisition(monkeypatch):
    gps_dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(
        gps_time_sync, "acquire_gps_time",
        lambda **kwargs: (gps_dt, GPSStatus(fix_status="A")),
    )
    return gps_dt


@pytest.mark.parametrize("flag", ["--status", "--no-set"])
def test_cli_display_modes_never_set_clock(monkeypatch, flag):
    fake_acquisition(monkeypatch)
    monkeypatch.setattr(
        gps_time_sync, "set_system_time",
        lambda value: pytest.fail("clock setter must not be called"),
    )
    assert gps_time_sync.cli([flag, "--port", "/dev/ttyFAKE"]) == 0


def test_cli_normal_mode_sets_clock_once(monkeypatch):
    expected = fake_acquisition(monkeypatch)
    calls = []
    monkeypatch.setattr(gps_time_sync, "set_system_time", calls.append)
    assert gps_time_sync.cli(["--port", "/dev/ttyFAKE"]) == 0
    assert calls == [expected]


@pytest.mark.parametrize(
    ("acquire_error", "set_error", "expected"),
    [
        (gps_time_sync.serial.SerialException("serial"), None, 2),
        (TimeoutError("timeout"), None, 3),
        (None, PermissionError("permission"), 4),
        (None, RuntimeError("clock"), 5),
    ],
)
def test_cli_error_exit_codes(monkeypatch, acquire_error, set_error, expected):
    if acquire_error is None:
        fake_acquisition(monkeypatch)
    else:
        monkeypatch.setattr(
            gps_time_sync, "acquire_gps_time",
            lambda **kwargs: (_ for _ in ()).throw(acquire_error),
        )
    if set_error is not None:
        monkeypatch.setattr(
            gps_time_sync, "set_system_time",
            lambda value: (_ for _ in ()).throw(set_error),
        )
    assert gps_time_sync.cli(["--port", "/dev/ttyFAKE"]) == expected


@pytest.mark.parametrize("option", ["--timeout", "--warmup", "--status-window"])
def test_cli_rejects_negative_durations(option):
    with pytest.raises(SystemExit) as exc_info:
        gps_time_sync.cli([option, "-1"])
    assert exc_info.value.code == 2
