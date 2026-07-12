from pathlib import Path

ROOT = Path(__file__).parents[1]
SERVICE_PATH = ROOT / "systemd" / "gps-time-sync.service"
TIMER_PATH = ROOT / "systemd" / "gps-time-sync.timer"
ENV_PATH = ROOT / "systemd" / "gps-time-sync.env.example"


def test_deployment_files_exist():
    assert SERVICE_PATH.is_file()
    assert TIMER_PATH.is_file()
    assert ENV_PATH.is_file()


def test_service_uses_documented_oneshot_wrapper():
    service = SERVICE_PATH.read_text()
    assert "Type=oneshot" in service
    assert "User=root" in service
    assert "EnvironmentFile=-/etc/default/gps-time-sync" in service
    assert "ExecStart=/opt/gps-time-sync-vk172/scripts/gps_sync.sh" in service
    assert "TimeoutStartSec=2min" in service
    assert "CapabilityBoundingSet=CAP_SYS_TIME" in service


def test_timer_targets_service_with_documented_cadence():
    timer = TIMER_PATH.read_text()
    assert "Unit=gps-time-sync.service" in timer
    assert "OnBootSec=2min" in timer
    assert "OnUnitActiveSec=15min" in timer
    assert "WantedBy=timers.target" in timer
    assert "Persistent=true" not in timer


def test_environment_example_contains_every_wrapper_variable():
    environment = ENV_PATH.read_text()
    assert "GPS_PORT=/dev/serial/by-id/replace-with-your-device" in environment
    assert "GPS_BAUDRATE=9600" in environment
    assert "GPS_TIMEOUT=60" in environment
    assert "GPS_WARMUP=2" in environment
    assert "GPS_STATUS_WINDOW=2" in environment
    assert "export " not in environment
    assert "$(" not in environment


def test_deployment_files_contain_no_unsafe_or_stale_content():
    content = "\n".join(
        path.read_text() for path in (SERVICE_PATH, TIMER_PATH, ENV_PATH)
    )
    assert "/home/rob" not in content
    assert "gps-time-syc-vk172" not in content
    assert "gps_time_syc_vk172" not in content
    assert ">>" not in content
    assert "2>&1" not in content
