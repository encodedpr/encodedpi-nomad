# encodedpi-nomad

Home Assistant configuration and supporting services for the `encodedpi` Raspberry Pi.

## Contents

- `homeassistant/packages/`: reusable sensors, templates, controls, MQTT publishing, and recorder policy.
- `homeassistant/automations/`: location, lighting, camera, timezone, and driving-mode automations.
- `homeassistant/dashboards/`: the Van Command YAML dashboard and Lovelace backup exports.
- `systemd/`: display, camera, Bluetooth, Kismet, timezone, and SSH-forwarding services.
- `service_scripts/`: scripts used by the systemd services.

## Deployment

These files are reference configurations, not a one-command installer. Review device-specific entity IDs, users, paths, interfaces, addresses, and hostnames before copying them.

- Home Assistant files normally go under `/config`.
- Service units go under `/etc/systemd/system`.
- Service scripts go under `/usr/local/bin` and must be executable.
- Run `systemctl daemon-reload` after changing service units.

To load the supplied Home Assistant directories:

```yaml
homeassistant:
  packages: !include_dir_named packages

automation: !include_dir_merge_list automations
```

`homeassistant/dashboards/van-command.yaml` is the active YAML-mode Van Command dashboard. The JSON dashboard files are `.storage` backup/transfer artifacts; do not copy them over a running Home Assistant instance.

## Safety

Secrets and generated runtime data must remain outside the repository. Do not commit `secrets.yaml`, `.storage`, databases, logs, private keys, camera captures, or diagnostic evidence.

The SSH forwarding service requires `/etc/default/encodedpi-port-forward`. Create it from `systemd/encodedpi-port-forward.env.example` and set `REMOTE_TARGET` locally.

Back up deployed files before replacing them.
