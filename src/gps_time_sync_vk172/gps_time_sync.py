"""
Utilities for synchronizing the system clock using a GK172 G-Mouse GPS dongle.

The module reads NMEA sentences from the USB GPS receiver, extracts the UTC
time from RMC messages, and optionally sets the system time. Changing the
system clock requires root privileges or the CAP_SYS_TIME capability.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

import serial  # type: ignore[import]

LOGGER = logging.getLogger(__name__)


def _calculate_nmea_checksum(data: str) -> int:
    """Return the XOR checksum for the supplied NMEA data portion."""
    checksum = 0
    for char in data:
        checksum ^= ord(char)
    return checksum


def _extract_nmea_fields(sentence: str) -> Optional[list[str]]:
    """
    Validate an NMEA sentence and return the data fields when the checksum is correct.
    """
    sentence = sentence.strip()
    if not sentence or not sentence.startswith("$"):
        return None

    try:
        data, checksum_text = sentence[1:].split("*")
    except ValueError:
        LOGGER.debug("Skipping malformed NMEA sentence: %s", sentence)
        return None

    computed_checksum = _calculate_nmea_checksum(data)
    try:
        transmitted_checksum = int(checksum_text[:2], 16)
    except ValueError:
        LOGGER.debug("Invalid checksum field in sentence: %s", sentence)
        return None

    if transmitted_checksum != computed_checksum:
        LOGGER.debug(
            "Checksum mismatch for %s (expected %02X, got %02X)",
            sentence,
            computed_checksum,
            transmitted_checksum,
        )
        return None

    return data.split(",")


def _safe_int(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _safe_float(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass
class RMCData:
    timestamp: Optional[dt.datetime]
    status: Optional[str]


@dataclass
class GGAData:
    fix_quality: Optional[int]
    satellites_in_use: Optional[int]
    hdop: Optional[float]


@dataclass
class GSAData:
    fix_mode: Optional[int]
    satellites_in_use: Optional[int]
    pdop: Optional[float]
    hdop: Optional[float]
    vdop: Optional[float]


@dataclass
class GSVData:
    satellites_in_view: Optional[int]


@dataclass
class GPSStatus:
    fix_status: Optional[str] = None
    fix_quality: Optional[int] = None
    fix_mode: Optional[int] = None
    satellites_in_use: Optional[int] = None
    satellites_in_view: Optional[int] = None
    hdop: Optional[float] = None
    pdop: Optional[float] = None
    vdop: Optional[float] = None

    def summary_lines(self) -> list[str]:
        """Return human-readable status lines for display in the CLI."""
        lines: list[str] = []

        status_map = {
            "A": "Active (valid fix)",
            "V": "Void (no fix)",
        }
        status_description = status_map.get(self.fix_status, "Unknown")
        lines.append(f"Fix status: {status_description}")

        fix_quality_map = {
            0: "Invalid",
            1: "GPS fix",
            2: "DGPS fix",
            3: "PPS fix",
            4: "RTK fixed",
            5: "RTK float",
            6: "Estimated",
            7: "Manual input",
            8: "Simulation",
        }
        if self.fix_quality is None:
            lines.append("Fix quality: Unknown")
        else:
            description = fix_quality_map.get(self.fix_quality, "Other")
            lines.append(f"Fix quality: {self.fix_quality} ({description})")

        fix_mode_map = {
            1: "No fix",
            2: "2D",
            3: "3D",
        }
        if self.fix_mode is None:
            lines.append("Fix mode: Unknown")
        else:
            description = fix_mode_map.get(self.fix_mode, "Other")
            lines.append(f"Fix mode: {self.fix_mode}D ({description})")

        if self.satellites_in_use is None:
            lines.append("Satellites in use: Unknown")
        else:
            lines.append(f"Satellites in use: {self.satellites_in_use}")

        if self.satellites_in_view is None:
            lines.append("Satellites in view: Unknown")
        else:
            lines.append(f"Satellites in view: {self.satellites_in_view}")

        if self.hdop is not None:
            lines.append(f"HDOP: {self.hdop:.2f}")
        if self.pdop is not None:
            lines.append(f"PDOP: {self.pdop:.2f}")
        if self.vdop is not None:
            lines.append(f"VDOP: {self.vdop:.2f}")

        return lines

    def has_detail_metrics(self) -> bool:
        """Return True when any detailed fix information beyond status is present."""
        return any(
            metric is not None
            for metric in (
                self.fix_quality,
                self.fix_mode,
                self.satellites_in_use,
                self.satellites_in_view,
                self.hdop,
                self.pdop,
                self.vdop,
            )
        )


def _parse_rmc_fields(fields: list[str], raw_sentence: str) -> Optional[RMCData]:
    if len(fields) < 10:
        LOGGER.debug("Not enough fields on RMC sentence: %s", raw_sentence)
        return None

    status = fields[2] or None
    data = RMCData(timestamp=None, status=status)

    time_utc = fields[1]
    date_utc = fields[9]

    if status != "A":
        LOGGER.debug("RMC status is not active (status=%s)", status)
        return data

    if not time_utc or not date_utc:
        LOGGER.debug("Missing time or date in RMC sentence: %s", raw_sentence)
        return data

    if len(date_utc) != 6:
        LOGGER.debug("Unexpected date format in RMC sentence: %s", raw_sentence)
        return data

    try:
        hour = int(time_utc[0:2])
        minute = int(time_utc[2:4])
        second = int(time_utc[4:6])
        fraction = time_utc[6:].lstrip(".") or "0"
        microsecond = int((fraction + "000000")[:6])

        day = int(date_utc[0:2])
        month = int(date_utc[2:4])
        year = int(date_utc[4:6])
    except ValueError:
        LOGGER.debug("Invalid numeric fields in RMC sentence: %s", raw_sentence)
        return data

    year += 2000 if year < 80 else 1900

    try:
        data.timestamp = dt.datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo=dt.timezone.utc,
        )
    except ValueError:
        LOGGER.debug("Constructed datetime is invalid from sentence: %s", raw_sentence)

    return data


def parse_rmc_sentence(sentence: str) -> Optional[RMCData]:
    fields = _extract_nmea_fields(sentence)
    if not fields or not fields[0].endswith("RMC"):
        return None
    return _parse_rmc_fields(fields, sentence)


def _parse_gga_fields(fields: list[str], raw_sentence: str) -> Optional[GGAData]:
    if len(fields) < 9:
        LOGGER.debug("Not enough fields on GGA sentence: %s", raw_sentence)
        return None

    fix_quality = _safe_int(fields[6]) if len(fields) > 6 else None
    satellites_in_use = _safe_int(fields[7]) if len(fields) > 7 else None
    hdop = _safe_float(fields[8]) if len(fields) > 8 else None
    return GGAData(
        fix_quality=fix_quality,
        satellites_in_use=satellites_in_use,
        hdop=hdop,
    )


def parse_gga_sentence(sentence: str) -> Optional[GGAData]:
    fields = _extract_nmea_fields(sentence)
    if not fields or not fields[0].endswith("GGA"):
        return None
    return _parse_gga_fields(fields, sentence)


def _parse_gsa_fields(fields: list[str], raw_sentence: str) -> Optional[GSAData]:
    if len(fields) < 17:
        LOGGER.debug("Not enough fields on GSA sentence: %s", raw_sentence)
        return None

    fix_mode = _safe_int(fields[2])
    satellites = [field for field in fields[3:15] if field]
    satellites_in_use = len(satellites) if satellites else None
    pdop = _safe_float(fields[15])
    hdop = _safe_float(fields[16]) if len(fields) > 16 else None
    vdop = _safe_float(fields[17]) if len(fields) > 17 else None

    return GSAData(
        fix_mode=fix_mode,
        satellites_in_use=satellites_in_use,
        pdop=pdop,
        hdop=hdop,
        vdop=vdop,
    )


def parse_gsa_sentence(sentence: str) -> Optional[GSAData]:
    fields = _extract_nmea_fields(sentence)
    if not fields or not fields[0].endswith("GSA"):
        return None
    return _parse_gsa_fields(fields, sentence)


def _parse_gsv_fields(fields: list[str], raw_sentence: str) -> Optional[GSVData]:
    if len(fields) < 4:
        LOGGER.debug("Not enough fields on GSV sentence: %s", raw_sentence)
        return None

    satellites_in_view = _safe_int(fields[3])
    return GSVData(satellites_in_view=satellites_in_view)


def parse_gsv_sentence(sentence: str) -> Optional[GSVData]:
    fields = _extract_nmea_fields(sentence)
    if not fields or not fields[0].endswith("GSV"):
        return None
    return _parse_gsv_fields(fields, sentence)


def acquire_gps_time(
    port: str,
    baudrate: int = 9600,
    timeout: float = 30.0,
    warmup: float = 2.0,
    require_detailed_status: bool = False,
) -> tuple[dt.datetime, GPSStatus]:
    """
    Read NMEA sentences from a GPS receiver until a valid UTC time is found.

    Args:
        port: Serial device path (e.g., /dev/ttyUSB0).
        baudrate: Baud rate for the serial connection (GK172 defaults to 9600).
        timeout: Maximum number of seconds to wait for a valid fix.
        warmup: Seconds to wait before parsing to let the GPS settle.

    Returns:
        A tuple of (timezone-aware datetime in UTC, GPSStatus summary).

    Raises:
        TimeoutError: When a valid RMC sentence is not observed before timeout.
        serial.SerialException: For serial communication errors.
    """
    LOGGER.info(
        "Connecting to GPS receiver on %s with baud %d (timeout=%.1fs)",
        port,
        baudrate,
        timeout,
    )

    status = GPSStatus()
    deadline = time.monotonic() + timeout
    with serial.Serial(port=port, baudrate=baudrate, timeout=1) as conn:
        if warmup > 0:
            LOGGER.debug("Warming up GPS stream for %.1f seconds", warmup)
            time.sleep(warmup)
            conn.reset_input_buffer()

        gps_time: Optional[dt.datetime] = None
        while time.monotonic() < deadline:
            raw = conn.readline()
            if not raw:
                continue

            try:
                sentence = raw.decode("ascii", errors="ignore").strip()
            except UnicodeDecodeError:
                LOGGER.debug("Skipping undecodable sentence: %r", raw)
                continue

            fields = _extract_nmea_fields(sentence)
            if not fields:
                continue

            message_type = fields[0][-3:]

            if message_type == "RMC":
                rmc = _parse_rmc_fields(fields, sentence)
                if rmc is None:
                    continue
                status.fix_status = rmc.status or status.fix_status
                if rmc.timestamp is not None and gps_time is None:
                    gps_time = rmc.timestamp
                    LOGGER.info("Received GPS time: %s", gps_time.isoformat())
                    if not require_detailed_status or status.has_detail_metrics():
                        return gps_time, status

            elif message_type == "GGA":
                gga = _parse_gga_fields(fields, sentence)
                if gga:
                    if gga.fix_quality is not None:
                        status.fix_quality = gga.fix_quality
                    if gga.satellites_in_use is not None:
                        status.satellites_in_use = gga.satellites_in_use
                    if gga.hdop is not None:
                        status.hdop = gga.hdop

            elif message_type == "GSA":
                gsa = _parse_gsa_fields(fields, sentence)
                if gsa:
                    if gsa.fix_mode is not None:
                        status.fix_mode = gsa.fix_mode
                    if gsa.satellites_in_use is not None:
                        status.satellites_in_use = gsa.satellites_in_use
                    if gsa.pdop is not None:
                        status.pdop = gsa.pdop
                    if gsa.hdop is not None:
                        status.hdop = gsa.hdop
                    if gsa.vdop is not None:
                        status.vdop = gsa.vdop

            elif message_type == "GSV":
                gsv = _parse_gsv_fields(fields, sentence)
                if gsv and gsv.satellites_in_view is not None:
                    status.satellites_in_view = gsv.satellites_in_view

            if gps_time is not None and (
                not require_detailed_status or status.has_detail_metrics()
            ):
                return gps_time, status

    if gps_time is not None:
        LOGGER.warning(
            "Timed out while waiting for detailed status; returning partial data."
        )
        return gps_time, status

    raise TimeoutError(f"Timed out waiting for GPS fix on {port}")


def set_system_time(target: dt.datetime) -> None:
    """
    Set the system clock to the supplied UTC datetime.

    Requires elevated privileges (root or CAP_SYS_TIME). Attempts to use
    clock_settime first, falling back to the `date` command when unavailable.
    """
    if target.tzinfo is None:
        raise ValueError("target datetime must be timezone-aware")

    timestamp = target.timestamp()
    try:
        time.clock_settime(time.CLOCK_REALTIME, timestamp)
        return
    except AttributeError:
        LOGGER.debug("clock_settime unavailable; falling back to date command")
    except PermissionError as exc:
        raise PermissionError(
            "Setting system time requires root privileges or CAP_SYS_TIME"
        ) from exc

    formatted = target.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(
        ["date", "-u", "-s", formatted],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Failed to set system time: {stderr or 'unknown error'}")


def cli(argv: Optional[list[str]] = None) -> int:
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize the system clock using a GK172 G-Mouse GPS receiver.\n"
            "Run with root privileges or CAP_SYS_TIME to allow clock updates."
        )
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        help="Serial device for the GPS (default: %(default)s)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=9600,
        help="Serial baud rate (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Seconds to wait for a valid GPS fix (default: %(default)s)",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=2.0,
        help="Seconds to wait after connecting before parsing sentences",
    )
    parser.add_argument(
        "--no-set",
        action="store_true",
        help="Only display the GPS time without changing the system clock",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display satellite/fix status and skip updating the system clock",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    skip_clock_update = args.no_set or args.status
    show_status = args.status

    try:
        gps_time, gps_status = acquire_gps_time(
            port=args.port,
            baudrate=args.baudrate,
            timeout=args.timeout,
            warmup=args.warmup,
            require_detailed_status=show_status,
        )
    except serial.SerialException as exc:
        LOGGER.error("Unable to communicate with GPS receiver: %s", exc)
        return 2
    except TimeoutError as exc:
        LOGGER.error(exc)
        return 3

    print(f"GPS UTC time: {gps_time.isoformat()}")
    local_time = gps_time.astimezone()
    print(f"Local time: {local_time.isoformat()}")

    if show_status:
        print()
        for line in gps_status.summary_lines():
            print(line)

    if skip_clock_update:
        return 0

    if hasattr(os, "geteuid"):
        try:
            if os.geteuid() != 0:
                LOGGER.warning(
                    "Not running as root. Clock adjustment will likely fail."
                )
        except OSError:
            LOGGER.debug("Could not determine effective UID")

    try:
        set_system_time(gps_time)
    except PermissionError as exc:
        LOGGER.error(exc)
        return 4
    except Exception as exc:  # pragma: no cover - unexpected path
        LOGGER.error("Failed to set system time: %s", exc)
        return 5

    LOGGER.info("System clock updated successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
