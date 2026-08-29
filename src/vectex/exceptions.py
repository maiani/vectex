"""Public exception hierarchy for vectex."""

from __future__ import annotations

from collections.abc import Sequence


class VectexError(Exception):
    """Base class for all expected vectex failures."""


class ConfigurationError(VectexError, ValueError):
    """A render option or component configuration is invalid."""


class MissingExecutableError(VectexError, FileNotFoundError):
    """An explicitly requested external executable cannot be found."""

    def __init__(self, tool: str, executable: str) -> None:
        self.tool = tool
        self.executable = executable
        super().__init__(
            f"Cannot find the {tool!r} executable {executable!r} on PATH. "
            "Install it or pass an executable override."
        )


class ExternalToolError(VectexError):
    """Base class for structured subprocess failures."""

    stage = "external tool"

    def __init__(
        self,
        message: str,
        *,
        argv: Sequence[str],
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
    ) -> None:
        self.argv = tuple(argv)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        diagnostic = stderr.strip() or stdout.strip()
        detail = f"{self.stage} failed: {message}"
        if diagnostic:
            detail += f"\n{diagnostic}"
        super().__init__(detail)


class CompilationError(ExternalToolError):
    """A source compiler failed or produced no usable artifact."""

    stage = "compilation"


class ConversionError(ExternalToolError):
    """An SVG converter failed or produced no usable artifact."""

    stage = "conversion"


class InvalidSVGError(VectexError, ValueError):
    """Converter output is not structurally valid SVG."""


class UnsafeSVGError(VectexError, ValueError):
    """Converter output contains active or non-self-contained content."""


class UnsupportedBackendError(VectexError, ImportError):
    """An optional backend is unavailable or unsupported."""
