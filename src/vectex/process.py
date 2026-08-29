"""Safe, shared external-process helpers."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
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
