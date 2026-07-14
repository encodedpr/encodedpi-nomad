from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 8765
HA_CONFIG = Path("/home/encoded/containers/homeassist/config/configuration.yaml")
ZONEINFO = Path("/usr/share/zoneinfo")


def run(cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def service_state(service):
    r = run(["systemctl", "is-active", service])
    return r.stdout.strip()


class Handler(BaseHTTPRequestHandler):

    def _ok(self, msg="ok"):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(msg.encode())

    def _service_action(self, action, service):
        result = run(["systemctl", action, service])
        if result.returncode == 0:
            return self._ok(service_state(service))
        self.send_error(500, result.stderr.strip() or "systemctl failed")

    def _service_enable(self, enabled, service):
        action = "enable" if enabled else "disable"
        result = run(["systemctl", action, "--now", service])
        if result.returncode == 0:
            return self._ok(service_state(service))
        self.send_error(500, result.stderr.strip() or "systemctl failed")

    def _display_mode(self, mode):
        if mode == "security":
            actions = [
                ("stop", "homeassistant-display.service"),
                ("start", "video_display_stream.service"),
            ]
        elif mode == "homeassistant":
            actions = [
                ("stop", "video_display_stream.service"),
                ("start", "homeassistant-display.service"),
            ]
        elif mode == "off":
            actions = [
                ("stop", "video_display_stream.service"),
                ("stop", "homeassistant-display.service"),
            ]
        else:
            return self.send_error(400, "invalid display mode")

        for action, service in actions:
            result = run(["systemctl", action, service])
            if result.returncode != 0:
                return self.send_error(500, result.stderr.strip() or "systemctl failed")
        return self._ok(mode)

    def _display_state(self):
        if service_state("video_display_stream.service") == "active":
            return "security"
        if service_state("homeassistant-display.service") == "active":
            return "homeassistant"
        return "off"

    def _timezone_from_request(self):
        parsed = urlparse(self.path)
        values = parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            values.update(parse_qs(body))
        return values.get("zone", [""])[0]

    def _valid_timezone(self, zone):
        if not re.fullmatch(r"[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)+", zone):
            return False
        try:
            candidate = (ZONEINFO / zone).resolve(strict=True)
            return ZONEINFO.resolve() in candidate.parents and candidate.is_file()
        except (FileNotFoundError, RuntimeError):
            return False

    def _write_ha_timezone(self, zone):
        original = HA_CONFIG.read_text(encoding="utf-8")
        lines = original.splitlines(keepends=True)
        start = next(
            (index for index, line in enumerate(lines) if line.rstrip() == "homeassistant:"),
            None,
        )
        if start is None:
            raise RuntimeError("homeassistant configuration block not found")

        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.strip() and not line.startswith((" ", "\t", "#")):
                end = index
                break

        timezone_line = None
        for index in range(start + 1, end):
            if re.match(r"^\s+time_zone\s*:", lines[index]):
                timezone_line = index
                break

        if timezone_line is None:
            lines.insert(start + 1, f"  time_zone: {zone}\n")
        else:
            newline = "\r\n" if lines[timezone_line].endswith("\r\n") else "\n"
            lines[timezone_line] = f"  time_zone: {zone}{newline}"

        stat = HA_CONFIG.stat()
        temporary = HA_CONFIG.with_name(f".{HA_CONFIG.name}.timezone.tmp")
        temporary.write_text("".join(lines), encoding="utf-8")
        os.chmod(temporary, stat.st_mode)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, HA_CONFIG)
        return original, stat

    def _restore_ha_config(self, original, stat):
        temporary = HA_CONFIG.with_name(f".{HA_CONFIG.name}.timezone.rollback")
        temporary.write_text(original, encoding="utf-8")
        os.chmod(temporary, stat.st_mode)
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, HA_CONFIG)

    def _update_timezone(self, zone):
        if not self._valid_timezone(zone):
            return self.send_error(400, "invalid IANA time zone")

        host_zone = run(["timedatectl", "show", "-p", "Timezone", "--value"])
        config_text = HA_CONFIG.read_text(encoding="utf-8")
        config_matches = re.search(
            rf"(?m)^\s+time_zone\s*:\s*{re.escape(zone)}\s*$", config_text
        )
        if host_zone.stdout.strip() == zone and config_matches:
            return self._ok(f"unchanged:{zone}")

        original, stat = self._write_ha_timezone(zone)
        check = run(
            [
                "docker",
                "exec",
                "homeassistant",
                "python",
                "-m",
                "homeassistant",
                "--script",
                "check_config",
                "-c",
                "/config",
            ],
            timeout=120,
        )
        if check.returncode != 0:
            self._restore_ha_config(original, stat)
            return self.send_error(500, check.stderr.strip() or "HA configuration invalid")

        result = run(["timedatectl", "set-timezone", zone])
        if result.returncode != 0:
            self._restore_ha_config(original, stat)
            return self.send_error(500, result.stderr.strip() or "timezone update failed")

        result = run(
            [
                "systemd-run",
                f"--unit=ha-timezone-restart-{int(time.time())}",
                "--on-active=2s",
                "/usr/bin/docker",
                "restart",
                "homeassistant",
            ]
        )
        if result.returncode != 0:
            return self.send_error(
                500, result.stderr.strip() or "HA restart scheduling failed"
            )
        return self._ok(f"updated:{zone}")

    def do_POST(self):

        if urlparse(self.path).path == "/timezone/update":
            return self._update_timezone(self._timezone_from_request())

        #
        # Kismet
        #
        if self.path == "/kismet/on":
            return self._service_enable(True, "kismet.service")

        elif self.path == "/kismet/off":
            return self._service_enable(False, "kismet.service")

        #
        # MJPEG Camera
        #
        elif self.path == "/mjpeg/on":
            return self._service_action("start", "mjpeg-camera.service")

        elif self.path == "/mjpeg/off":
            return self._service_action("stop", "mjpeg-camera.service")

        elif self.path == "/mjpeg/restart":
            return self._service_action("restart", "mjpeg-camera.service")

        elif self.path == "/security/restart":
            result = run(["systemctl", "restart", "mjpeg-camera.service"])
            if result.returncode != 0:
                return self.send_error(500, result.stderr.strip() or "stream restart failed")
            result = run(["systemctl", "restart", "video_display_stream.service"])
            if result.returncode != 0:
                return self.send_error(500, result.stderr.strip() or "display restart failed")
            return self._ok("active")

        elif self.path == "/display/security":
            return self._display_mode("security")

        elif self.path == "/display/homeassistant":
            return self._display_mode("homeassistant")

        elif self.path == "/display/off":
            return self._display_mode("off")

        #
        # Reboot
        #
        elif self.path == "/reboot":
            result = run(["systemctl", "reboot"])
            if result.returncode == 0:
                return self._ok()
            self.send_error(500, result.stderr.strip() or "reboot failed")

        self.send_response(404)
        self.end_headers()

    def do_GET(self):

        #
        # Kismet state
        #
        if self.path == "/kismet/state":
            return self._ok(service_state("kismet"))

        #
        # MJPEG state
        #
        elif self.path == "/mjpeg/state":
            return self._ok(service_state("mjpeg-camera.service"))

        elif self.path == "/display/state":
            return self._ok(self._display_state())

        elif self.path == "/timezone/state":
            result = run(["timedatectl", "show", "-p", "Timezone", "--value"])
            if result.returncode == 0:
                return self._ok(result.stdout.strip())
            return self.send_error(500, result.stderr.strip() or "timezone query failed")

        self.send_response(404)
        self.end_headers()


ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
