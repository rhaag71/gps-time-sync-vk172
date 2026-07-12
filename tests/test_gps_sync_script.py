import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "gps_sync.sh"
CONFIG_ENV = {
    "GPS_PORT",
    "GPS_BAUDRATE",
    "GPS_TIMEOUT",
    "GPS_WARMUP",
    "GPS_STATUS_WINDOW",
}
DEFAULT_ARGS = [
    "--port",
    "/dev/ttyACM0",
    "--baudrate",
    "9600",
    "--timeout",
    "60",
    "--warmup",
    "2",
    "--status-window",
    "2",
]


def make_fake_repo(tmp_path: Path, *, executable: bool = True) -> tuple[Path, Path]:
    script = tmp_path / "scripts" / "gps_sync.sh"
    script.parent.mkdir()
    shutil.copy2(SCRIPT, script)
    script.chmod(0o755)

    args_file = tmp_path / "received-args"
    if executable:
        fake_cli = tmp_path / ".venv" / "bin" / "gps-time-sync"
        fake_cli.parent.mkdir(parents=True)
        fake_cli.write_text(
            "#!/usr/bin/env bash\n"
            'printf \'%s\\0\' "$@" > "$GPS_ARGS_FILE"\n'
            'exit "${GPS_CHILD_EXIT:-0}"\n'
        )
        fake_cli.chmod(0o755)
    return script, args_file


def run_script(
    script: Path,
    args_file: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    for name in CONFIG_ENV:
        process_env.pop(name, None)
    process_env["GPS_ARGS_FILE"] = str(args_file)
    process_env.update(env or {})
    return subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        env=process_env,
        check=False,
    )


def recorded_args(args_file: Path) -> list[str]:
    return args_file.read_bytes().rstrip(b"\0").decode().split("\0")


def test_help_succeeds_without_virtual_environment(tmp_path):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, "--help")
    assert result.returncode == 0
    assert (
        "command-line options > environment variables > built-in defaults"
        in result.stdout
    )
    assert "GPS_STATUS_WINDOW" in result.stdout


def test_built_in_defaults_are_passed_exactly(tmp_path):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(script, args_file)
    assert result.returncode == 0
    assert recorded_args(args_file) == DEFAULT_ARGS


def test_environment_overrides_defaults(tmp_path):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(
        script,
        args_file,
        env={
            "GPS_PORT": "/dev/env-gps",
            "GPS_BAUDRATE": "4800",
            "GPS_TIMEOUT": "10.5",
            "GPS_WARMUP": ".25",
            "GPS_STATUS_WINDOW": "3.0",
        },
    )
    assert result.returncode == 0
    assert recorded_args(args_file) == [
        "--port",
        "/dev/env-gps",
        "--baudrate",
        "4800",
        "--timeout",
        "10.5",
        "--warmup",
        ".25",
        "--status-window",
        "3.0",
    ]


def test_command_line_overrides_environment(tmp_path):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(
        script,
        args_file,
        "--port",
        "/dev/cli-gps",
        "--baudrate",
        "19200",
        "--timeout",
        "20",
        "--warmup",
        "1.5",
        "--status-window",
        "4",
        env={
            "GPS_PORT": "/dev/env-gps",
            "GPS_BAUDRATE": "4800",
            "GPS_TIMEOUT": "10",
            "GPS_WARMUP": "1",
            "GPS_STATUS_WINDOW": "3",
        },
    )
    assert result.returncode == 0
    assert recorded_args(args_file) == [
        "--port",
        "/dev/cli-gps",
        "--baudrate",
        "19200",
        "--timeout",
        "20",
        "--warmup",
        "1.5",
        "--status-window",
        "4",
    ]


@pytest.mark.parametrize(
    "port",
    [
        "/dev/serial/by-id/usb-u-blox_GPS-if00",
        "/dev/serial/by-id/GPS receiver with spaces",
    ],
)
def test_device_paths_are_preserved_as_one_argument(tmp_path, port):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(script, args_file, "--port", port)
    assert result.returncode == 0
    assert recorded_args(args_file)[1] == port


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (("--status",), ["--status"]),
        (("--no-set",), ["--no-set"]),
        (("--verbose",), ["--verbose"]),
        (("--status", "--no-set", "--verbose"), ["--status", "--no-set", "--verbose"]),
    ],
)
def test_boolean_flags_are_passed_through(tmp_path, flags, expected):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(script, args_file, *flags)
    assert result.returncode == 0
    assert recorded_args(args_file) == DEFAULT_ARGS + expected


@pytest.mark.parametrize(
    "option", ["--port", "--baudrate", "--timeout", "--warmup", "--status-window"]
)
def test_missing_option_values_fail_clearly(tmp_path, option):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, option)
    assert result.returncode == 64
    assert f"{option} requires a value" in result.stderr


def test_option_followed_by_another_option_is_a_missing_value(tmp_path):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, "--port", "--status")
    assert result.returncode == 64
    assert "--port requires a value" in result.stderr


def test_unknown_option_fails_clearly(tmp_path):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, "--unknown")
    assert result.returncode == 64
    assert "unknown option: --unknown" in result.stderr


@pytest.mark.parametrize("baudrate", ["invalid", "0", "000", "-9600", "9600.5"])
def test_invalid_baud_rate_fails(tmp_path, baudrate):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, "--baudrate", baudrate)
    assert result.returncode == 64
    assert "baud rate must be a positive integer" in result.stderr


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--timeout", "-1", "timeout"),
        ("--warmup", "-1", "warmup"),
        ("--status-window", "-1", "status window"),
        ("--timeout", "nan", "timeout"),
    ],
)
def test_invalid_non_negative_numbers_fail(tmp_path, option, value, message):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file, option, value)
    assert result.returncode == 64
    assert f"{message} must be a non-negative number" in result.stderr


@pytest.mark.parametrize("value", ["0", "0.0", ".5", "1.", "12.25"])
def test_non_negative_number_boundaries_are_accepted(tmp_path, value):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(
        script,
        args_file,
        "--timeout",
        value,
        "--warmup",
        value,
        "--status-window",
        value,
    )
    assert result.returncode == 0
    received = recorded_args(args_file)
    assert received[5] == value
    assert received[7] == value
    assert received[9] == value


def test_missing_virtual_environment_preserves_exit_code(tmp_path):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    result = run_script(script, args_file)
    assert result.returncode == 1
    assert f"Virtual environment not found at {tmp_path / '.venv'}" in result.stderr


def test_missing_executable_preserves_exit_code(tmp_path):
    script, args_file = make_fake_repo(tmp_path, executable=False)
    (tmp_path / ".venv").mkdir()
    result = run_script(script, args_file)
    assert result.returncode == 2
    assert "gps-time-sync executable not found" in result.stderr


def test_child_exit_code_is_returned_through_exec(tmp_path):
    script, args_file = make_fake_repo(tmp_path)
    result = run_script(script, args_file, env={"GPS_CHILD_EXIT": "23"})
    assert result.returncode == 23


def test_shell_metacharacters_are_passed_literally(tmp_path):
    script, args_file = make_fake_repo(tmp_path)
    marker = tmp_path / "must-not-exist"
    value = f"$(touch {marker}); $HOME * [abc]"
    result = run_script(script, args_file, env={"GPS_PORT": value})
    assert result.returncode == 0
    assert recorded_args(args_file)[1] == value
    assert not marker.exists()
