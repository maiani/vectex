"""Converter interface and dvisvgm implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .compiler import CompilationResult
from .exceptions import ConfigurationError, ConversionError
from .process import find_executable, run_process


@dataclass(frozen=True, slots=True)
class ConvertRequest:
    """Inputs shared by converter implementations."""

    compiled: CompilationResult
    workdir: Path
    timeout: float
    extra_args: tuple[str, ...] = ()
    executable: str | None = None


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """A successfully produced SVG document."""

    path: Path
    converter: str
    argv: tuple[str, ...]
    stdout: str
    stderr: str


@runtime_checkable
class Converter(Protocol):
    """Extensible intermediate-to-SVG converter interface."""

    @property
    def name(self) -> str: ...

    def convert(self, request: ConvertRequest) -> ConversionResult: ...


class DvisvgmConverter:
    """Convert a PDF intermediate to path-oriented SVG with dvisvgm."""

    name = "dvisvgm"

    def convert(self, request: ConvertRequest) -> ConversionResult:
        if request.compiled.format != "pdf":
            raise ConfigurationError(
                f"dvisvgm expects a PDF intermediate, got {request.compiled.format!r}"
            )
        executable = find_executable(self.name, request.executable or self.name)
        output_path = request.workdir / "document.svg"
        argv = (
            executable,
            "--pdf",
            "--page=1",
            "--bbox=min",
            "--exact",
            "--no-fonts",
            *request.extra_args,
            f"--output={output_path}",
            str(request.compiled.path),
        )
        completed = run_process(
            argv,
            cwd=request.workdir,
            timeout=request.timeout,
            error_type=ConversionError,
        )
        if not output_path.is_file():
            raise ConversionError(
                "converter reported success but did not create document.svg",
                argv=argv,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return ConversionResult(
            path=output_path,
            converter=self.name,
            argv=argv,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def converter_from_name(name: str) -> Converter:
    """Construct a built-in converter by public name."""
    if name != "dvisvgm":
        raise ConfigurationError(f"Unsupported converter: {name!r}")
    return DvisvgmConverter()
