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
        return self._convert(request, page_count=1, batch=False)[0]

    def convert_many(self, request: ConvertRequest) -> tuple[ConversionResult, ...]:
        """Convert every compiled PDF page in one dvisvgm process."""
        return self._convert(
            request, page_count=request.compiled.page_count, batch=True
        )

    def _convert(
        self, request: ConvertRequest, *, page_count: int, batch: bool
    ) -> tuple[ConversionResult, ...]:
        if request.compiled.format != "pdf":
            raise ConfigurationError(
                f"dvisvgm expects a PDF intermediate, got {request.compiled.format!r}"
            )
        executable = find_executable(self.name, request.executable or self.name)
        if page_count < 1:
            raise ConfigurationError("compiled page_count must be positive")
        output_pattern = request.workdir / (
            "document-%p.svg" if batch else "document.svg"
        )
        argv = (
            executable,
            "--pdf",
            f"--page=1-{page_count}" if batch else "--page=1",
            "--bbox=min",
            "--exact",
            "--no-fonts",
            *request.extra_args,
            f"--output={output_pattern}",
            str(request.compiled.path),
        )
        completed = run_process(
            argv,
            cwd=request.workdir,
            timeout=request.timeout,
            error_type=ConversionError,
        )
        output_paths = (
            tuple(
                request.workdir / f"document-{page}.svg"
                for page in range(1, page_count + 1)
            )
            if batch
            else (request.workdir / "document.svg",)
        )
        if not all(path.is_file() for path in output_paths):
            raise ConversionError(
                "converter reported success but did not create every SVG page",
                argv=argv,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return tuple(
            ConversionResult(
                path=path,
                converter=self.name,
                argv=argv,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            for path in output_paths
        )


def converter_from_name(name: str) -> Converter:
    """Construct a built-in converter by public name."""
    if name != "dvisvgm":
        raise ConfigurationError(f"Unsupported converter: {name!r}")
    return DvisvgmConverter()
