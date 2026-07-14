# encodedpi-nomad

Configuration, services, and maintenance tooling used by an `encodedpi` Raspberry Pi for remote and nomadic operation.

## Layout

- `homeassistant/packages/`: reusable Home Assistant packages grouped by function.
- `homeassistant/automations/`: reusable automation lists grouped by function.
- `homeassistant/examples/`: instance-specific examples that should be reviewed before use.
- `homeassistant/dashboards/`: current Lovelace storage exports for the active Overview and Map dashboards, dashboard registry, and frontend resources.
- `systemd/`: custom systemd units for Kismet, displays, video streaming, MJPEG, timezone updates, and Home Assistant forwarding.
- `service_scripts/`: runtime helpers required by the deployed services, Bluetooth handling, the local control API, and the MJPEG server.

## Safety

Runtime secrets and generated state are intentionally excluded. Do not commit Home Assistant `secrets.yaml`, `.storage`, databases, exports, logs, private keys, or captured evidence. Review hostnames, interface names, private IP addresses, paths, and service users before installing on another device.

The SSH forwarding service reads its destination from `/etc/default/encodedpi-port-forward`. Copy `systemd/encodedpi-port-forward.env.example` to that location and set `REMOTE_TARGET` locally; do not commit the real value.

### Migration from the original EncodedPi units

The local control API was previously installed as `kismet-agent.service` with `/usr/local/bin/kismet-agent.py`. It also controls displays, MJPEG, reboot, and timezone, so the repository uses the clearer `encodedpi-control-api` name. Stop and disable the legacy unit before enabling the replacement; the new unit also declares an explicit conflict to prevent both processes from binding `127.0.0.1:8765`.

The current Pi runs `mjpeg_server.py` from `/home/encoded`; this repository standardizes service helpers under `/usr/local/bin`. Install the new script before replacing or restarting `mjpeg-camera.service`. Create `/etc/default/encodedpi-port-forward` before replacing the SSH forwarding unit, otherwise the required `REMOTE_TARGET` value will be missing.

## Installation

Treat the files as reference configurations rather than a one-command installer. Copy only the required fragments to the target host, adjust environment-specific values, validate them, and then enable the corresponding systemd units.

Typical destinations are `/config` for Home Assistant, `/etc/systemd/system` for units, and `/usr/local/bin` for service helpers.

The service units assume Debian/Raspberry Pi OS paths and require `python3`, `curl`, `openssh-client`, `ffmpeg`/`ffplay`, `netcat`, and the Bluetooth utilities used by the watchdog. `mjpeg_server.py` additionally requires PyGObject, GStreamer 1.0, the GStreamer V4L2 and JPEG plugins, and access to `/dev/video0`. Install the helpers as executable files in `/usr/local/bin`, then run `systemctl daemon-reload` before enabling their units or timers.

### Home Assistant packages

Copy any desired files from `homeassistant/packages/` into a `packages` directory in the target Home Assistant configuration. Enable package loading once in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

The packages are intentionally separated by function:

- `system_control.yaml`: shell commands and command-line switches backed by the local control API.
- `dynamic_timezone.yaml`: GPS-aware time-zone REST sensor and the shell command that updates the host and Home Assistant.
- `internet_location_rest.yaml`: REST sensors for ISP, geolocation, and space-weather data.
- `camera_motion.yaml`: MJPEG/FFmpeg motion detection.
- `power_energy_sensors.yaml`: integration and utility-meter energy sensors.
- `van_derived_sensors.yaml`: template sensors and binary sensors derived from device entities.
- `blackbox_mqtt_publishing.yaml`: the curated MQTT state-stream feed.
- `recorder_policy.yaml`: recorder exclusions for noisy or mirrored sensors.
- `homeassistant_http_security.yaml`: optional HTTP proxy hardening.

Each package can be enabled or omitted independently. Entity IDs and local endpoints remain deployment-specific and should be reviewed before copying a package to another instance.

### Home Assistant automations

Copy the desired files from `homeassistant/automations/` into the target instance and merge them from `configuration.yaml`:

```yaml
automation: !include_dir_merge_list automations
```

The automation files are separated into `location_and_rest`, `dynamic_timezone`, `lighting`, `security_camera`, and `driving_mode`. They contain one canonical version of each automation; the older duplicate lists and the superseded blackbox publishing automations are not included.

### Lovelace dashboards

`homeassistant/dashboards/van-command.yaml` is the active YAML-mode Van Command
dashboard. Configure it under `lovelace.dashboards` and copy it to the path used
by that dashboard's `filename` setting.

The dashboard JSON files are exports of Home Assistant `.storage` records:

- `overview.json`: active Overview dashboard (`lovelace.lovelace`).
- `map.json`: active Map dashboard (`lovelace.map`).
- `dashboards.json`: dashboard registry and sidebar metadata.
- `resources.json`: Lovelace frontend resources.

These are backup/transfer artifacts, not YAML-mode dashboards. Do not overwrite a running instance's `.storage` files. Stop Home Assistant, back up the destination, restore only the intended records using their `key` values, preserve ownership and permissions, and validate the instance before starting it again.
