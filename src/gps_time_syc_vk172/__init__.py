"""GPS time synchronization utilities for the VK172 USB dongle."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("gps-time-syc-vk172")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


def main() -> None:
    """Entry point for ``python -m gps_time_syc_vk172``."""
    print(
        "gps_time_syc_vk172 package loaded. See gps-time-sync CLI for GPS time sync."
    )


if __name__ == "__main__":  # pragma: no cover
    main()
