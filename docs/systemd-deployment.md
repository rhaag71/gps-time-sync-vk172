# systemd Deployment

This guide installs `gps-time-sync-vk172` as a root-run oneshot service in a controlled, system-owned directory. A timer starts it two minutes after boot and then every 15 minutes. The service writes normal output and errors to the systemd journal; it does not manage a separate log file.

Cron remains a simpler alternative in the [main README](../README.md). Use only one automation method for a given installation.

## Privilege model

The supplied unit runs as root. This is the simplest reliable model for setting the system clock, but it makes installation ownership important: do not run the unit from a casually mutable development checkout in a user's home directory. The example uses `/opt/gps-time-sync-vk172`, which should be writable only through deliberate administrative updates.

Two permissions are involved:

- **Serial-device access:** the process must be able to open the selected `/dev/serial/...`, `/dev/ttyACM*`, or `/dev/ttyUSB*` device. Device ownership, udev rules, ACLs, and groups such as `dialout` control this access.
- **Clock-setting privilege:** normal mode needs root or `CAP_SYS_TIME`. Serial access alone does not permit clock changes.

The unit starts as root but bounds its capabilities to `CAP_SYS_TIME`, prevents privilege gains, hides home directories, and applies conservative kernel/control-group protections. It deliberately does not use `PrivateDevices=true`, because that would hide the GPS serial device.

A non-root service is an advanced alternative, not a drop-in edit. It requires both explicit serial access (for example, a suitable device group/udev rule or ACL) and a carefully reviewed `CAP_SYS_TIME` design. Assigning capabilities to a shared Python interpreter can affect more than this project, and adding `AmbientCapabilities=CAP_SYS_TIME` to a service must be evaluated with the selected user, executable, filesystem ownership, and local security policy. The repository does not ship a non-root unit because that complete privilege model is site-specific.

## 1. Install in a controlled directory

Clone and install as an administrator:

```bash
sudo git clone https://github.com/rhaag71/gps-time-sync-vk172.git /opt/gps-time-sync-vk172
sudo python3 -m venv /opt/gps-time-sync-vk172/.venv
sudo /opt/gps-time-sync-vk172/.venv/bin/python -m pip install --upgrade pip
sudo /opt/gps-time-sync-vk172/.venv/bin/python -m pip install -e /opt/gps-time-sync-vk172
cd /opt/gps-time-sync-vk172
```

Keep `/opt/gps-time-sync-vk172` and its virtual environment controlled by root or another trusted deployment process. If you choose another installation directory, edit the absolute `ExecStart=` path in the service before installing it. systemd does not expand arbitrary shell variables in `ExecStart=`.

## 2. Identify a stable GPS device

Connect the receiver and inspect:

```bash
ls -l /dev/serial/by-id/
```

Prefer the matching `/dev/serial/by-id/...` path over a connection-order-dependent name such as `/dev/ttyACM0` or `/dev/ttyUSB0`.

## 3. Install the environment file

Copy the example and edit the device path:

```bash
sudo install -m 0644 systemd/gps-time-sync.env.example /etc/default/gps-time-sync
sudo editor /etc/default/gps-time-sync
```

The file supports the existing wrapper variables:

```text
GPS_PORT=/dev/serial/by-id/replace-with-your-device
GPS_BAUDRATE=9600
GPS_TIMEOUT=60
GPS_WARMUP=2
GPS_STATUS_WINDOW=2
```

Use systemd-compatible `KEY=value` entries only—no `export`, command substitution, or shell commands. The service marks the file optional so wrapper defaults still work if it is absent, but unattended installations should set a stable device path explicitly.

## 4. Install and enable the units

From `/opt/gps-time-sync-vk172`:

```bash
sudo install -m 0644 systemd/gps-time-sync.service /etc/systemd/system/gps-time-sync.service
sudo install -m 0644 systemd/gps-time-sync.timer /etc/systemd/system/gps-time-sync.timer
sudo systemctl daemon-reload
sudo systemctl enable --now gps-time-sync.timer
```

The installed service's `ExecStart=` is:

```text
/opt/gps-time-sync-vk172/scripts/gps_sync.sh
```

Adjust that absolute path in `/etc/systemd/system/gps-time-sync.service` if your controlled installation is elsewhere, then run `sudo systemctl daemon-reload` again.

## 5. Test and inspect the deployment

Run one synchronization manually:

```bash
sudo systemctl start gps-time-sync.service
```

Inspect service and timer state:

```bash
systemctl status gps-time-sync.service
systemctl status gps-time-sync.timer
systemctl list-timers gps-time-sync.timer
```

Read journal output:

```bash
journalctl -u gps-time-sync.service
journalctl -u gps-time-sync.service --since today
```

The service is `Type=oneshot`: after success it becomes inactive until the next timer event. A failure is recorded in service status and the journal. There is no restart loop; the timer remains enabled and attempts the next scheduled run. `TimeoutStartSec=2min` bounds a stuck invocation.

## Timer cadence and ordering

The timer uses:

- `OnBootSec=2min` to allow boot and device discovery to settle;
- `OnUnitActiveSec=15min` for a conservative recurring cadence; and
- `AccuracySec=30s` so systemd may coalesce wakeups slightly.

This is a monotonic schedule. `Persistent=true` is intentionally not used: missed periodic invocations do not need to be replayed, and the boot trigger starts a fresh cadence after every boot. The service orders itself after `local-fs.target` so the controlled checkout and configuration are available. The two-minute boot delay is expected to cover ordinary USB enumeration; unusual hardware may need site-specific device ordering or a longer delay.

## Other time services

`systemd-timesyncd`, Chrony, `ntpd`, or another time daemon may adjust the clock immediately after this oneshot service. Choose deliberately which source is authoritative. Depending on the host's purpose, that can mean:

- disabling a competing network-time service;
- configuring Chrony to use a properly integrated GPS/refclock/PPS source instead of periodically forcing the clock with this utility; or
- using this utility only for offline or bootstrap synchronization before another service takes responsibility.

This project does not expose a Chrony refclock source or PPS integration, and the supplied units do not disable or reconfigure other services automatically.

## Disable and remove the deployment

Disable future timer runs and stop any active service:

```bash
sudo systemctl disable --now gps-time-sync.timer
sudo systemctl stop gps-time-sync.service
```

To remove the unit/configuration files as well:

```bash
sudo rm /etc/systemd/system/gps-time-sync.service
sudo rm /etc/systemd/system/gps-time-sync.timer
sudo rm /etc/default/gps-time-sync
sudo systemctl daemon-reload
sudo systemctl reset-failed gps-time-sync.service
```

Removing `/opt/gps-time-sync-vk172` is a separate administrative decision; preserve it if it contains changes or logs relevant to your deployment process.
