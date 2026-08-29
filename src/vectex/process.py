"""Safe, shared external-process helpers."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import TypeVar

from .exceptions import ExternalToolError, MissingExecutableError

ProcessFailure = TypeVar("ProcessFailure", bound=ExternalToolError)


def find_executable(tool: str, executable: str) -> str:
    """Resolve *executable* explicitly or raise a structured error."""
    resolved = shutil.which(executable)
    if resolved is None:
        raise MissingExecutableError(tool, executable)
    return resolved


@cache
def tool_identity(executable: str, *, timeout: float = 10.0) -> str:
    """Identify an installed tool for cache keys: its real path and version.

    A cached fragment compiled by one TeX or dvisvgm installation must not be
    served after that installation changes, so the identity of the executable
    belongs in the cache key alongside the source. Probing is memoized per
    process, and a tool that cannot report a version degrades to its path.
    """
    resolved = str(Path(shutil.which(executable) or executable).resolve())
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return resolved
    report = (completed.stdout or completed.stderr or "").strip().splitlines()
    return f"{resolved}|{report[0].strip()}" if report else resolved


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    error_type: type[ProcessFailure],
) -> subprocess.CompletedProcess[str]:
    """Run an argv list without a shell and translate failures."""
    args = [str(arg) for arg in argv]
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _text(exc.stdout)
        stderr = _text(exc.stderr)
        raise error_type(
            f"timed out after {timeout:g} seconds",
            argv=args,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        ) from exc
    if completed.returncode != 0:
        raise error_type(
            f"process exited with status {completed.returncode}",
            argv=args,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
