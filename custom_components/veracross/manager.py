"""Runs the vx_ha_cli Go binary and parses its JSON output.

The binary is a thin wrapper around the vx_puppet Go library: it spins up
lightpanda (a tiny headless browser, downloaded on first run), logs into
Veracross, scrapes grades, and prints one JSON line to stdout:

    {"ok": true, "grades": [{"class": ..., "gradeLetter": ..., "grade": ..., "new_updates": ...}]}
    {"ok": false, "error": "..."}

We always pick the last non-empty stdout line to be resilient to any
incidental logging the binary/lightpanda might emit before that.
"""
from __future__ import annotations

import json
import logging
import platform
import os, stat
from dataclasses import dataclass, field
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    BINARY_DIR_NAME,
    BINARY_PREFIX,
    DEFAULT_TIMEOUT_S,
    SIGNAL_GRADES_UPDATED,
    SIGNAL_UPDATING_STATE,
)

_LOGGER = logging.getLogger(__name__)


class VeracrossError(Exception):
    """Raised when the CLI reports a failure or can't be run at all."""


def _binary_arch() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    raise VeracrossError(f"unsupported host architecture: {machine}")


@dataclass
class VeracrossManager:
    """Owns login creds for one config entry and knows how to fetch grades."""

    hass: HomeAssistant
    entry_id: str
    school: str
    username: str
    password: str

    grades: list[dict] = field(default_factory=list)
    last_error: str | None = None
    updating: bool = False

    def _binary_path(self) -> Path:
        integration_dir = Path(__file__).parent
        arch = _binary_arch()
        path = integration_dir / BINARY_DIR_NAME / f"{BINARY_PREFIX}{arch}"
        if not path.exists():
            raise VeracrossError(f"bundled binary missing for arch {arch}: {path}")
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def _lightpanda_dir(self) -> str:
        # Persist the downloaded lightpanda binary across restarts, and keep
        # it out of the integration's own (read-only-ish) folder.
        return self.hass.config.path("veracross_lightpanda")

    async def async_fetch_grades(self) -> list[dict]:
        """Run the CLI once. Raises VeracrossError on any failure."""
        self._set_updating(True)
        try:
            grades = await self.hass.async_add_executor_job(self._run_cli_blocking)
            self.grades = grades
            self.last_error = None
            async_dispatcher_send(
                self.hass, SIGNAL_GRADES_UPDATED.format(entry_id=self.entry_id), grades
            )
            return grades
        except VeracrossError as err:
            self.last_error = str(err)
            raise
        finally:
            self._set_updating(False)

    def _set_updating(self, value: bool) -> None:
        self.updating = value
        async_dispatcher_send(
            self.hass, SIGNAL_UPDATING_STATE.format(entry_id=self.entry_id), value
        )

    def _run_cli_blocking(self) -> list[dict]:
        path = self._lightpanda_dir() + "/lightpanda"
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        binary = self._binary_path()
        args = [
            str(binary),
            "-school", self.school,
            "-user", self.username,
            "-pass", self.password,
            "-timeout", f"{DEFAULT_TIMEOUT_S}s",
            "-lightpanda-dir", self._lightpanda_dir(),
        ]

        import subprocess

        try:
            proc = _run_sync(args, timeout=DEFAULT_TIMEOUT_S + 30)
        except subprocess.TimeoutExpired as err:
            raise VeracrossError("timed out waiting for veracross login/scrape") from err
        except OSError as err:
            raise VeracrossError(f"failed to launch vx_ha_cli: {err}") from err

        stdout, stderr, returncode = proc

        line = ""
        for candidate in reversed(stdout.strip().splitlines()):
            if candidate.strip():
                line = candidate.strip()
                break

        if not line:
            _LOGGER.error("vx_ha_cli produced no output. stderr: %s", stderr)
            raise VeracrossError("no output from vx_ha_cli (see logs)")

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as err:
            _LOGGER.error("vx_ha_cli non-JSON output: %s / stderr: %s", line, stderr)
            raise VeracrossError(f"could not parse vx_ha_cli output: {err}") from err

        if not payload.get("ok"):
            raise VeracrossError(payload.get("error", "unknown error"))

        return payload.get("grades", [])


def _run_sync(args: list[str], timeout: int) -> tuple[str, str, int]:
    """Blocking subprocess run, meant for async_add_executor_job."""
    import subprocess

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode
