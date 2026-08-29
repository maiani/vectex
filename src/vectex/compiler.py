"""Compiler interfaces and built-in TeX/Typst implementations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .exceptions import CompilationError, ConfigurationError
from .process import find_executable, run_process


@dataclass(frozen=True, slots=True)
class CompileRequest:
    """Inputs shared by compiler implementations."""

    source: str
    workdir: Path
    timeout: float
    preamble: str = ""
    math_mode: bool = True
    extra_args: tuple[str, ...] = ()
    executable: str | None = None


@dataclass(frozen=True, slots=True)
class CompilationResult:
    """A successfully compiled intermediate artifact."""

    path: Path
    format: str
    engine: str
    argv: tuple[str, ...]
    stdout: str
    stderr: str


@runtime_checkable
class Compiler(Protocol):
    """Extensible source-compiler interface."""

    @property
    def name(self) -> str: ...

    def compile(self, request: CompileRequest) -> CompilationResult: ...


class TeXCompiler:
    """Compile an expression with pdflatex, xelatex, or lualatex."""

    _SUPPORTED = frozenset({"pdflatex", "xelatex", "lualatex"})

    def __init__(self, engine: str) -> None:
        if engine not in self._SUPPORTED:
            raise ConfigurationError(f"Unsupported TeX engine: {engine!r}")
        self._name = engine

    @property
    def name(self) -> str:
        return self._name

    def compile(self, request: CompileRequest) -> CompilationResult:
        executable = find_executable(self.name, request.executable or self.name)
        input_path = request.workdir / "document.tex"
        output_path = request.workdir / "document.pdf"
        input_path.write_text(
            _tex_document(request.source, request.preamble, request.math_mode),
            encoding="utf-8",
        )
        argv = (
            executable,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-no-shell-escape",
            f"-output-directory={request.workdir}",
            *request.extra_args,
            str(input_path),
        )
        completed = run_process(
            argv,
            cwd=request.workdir,
            timeout=request.timeout,
            error_type=CompilationError,
        )
        if not output_path.is_file():
            raise CompilationError(
                "compiler reported success but did not create document.pdf",
                argv=argv,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return CompilationResult(
            path=output_path,
            format="pdf",
            engine=self.name,
            argv=argv,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class TypstCompiler:
    """Compile a Typst source string to PDF."""

    name = "typst"

    def compile(self, request: CompileRequest) -> CompilationResult:
        executable = find_executable(self.name, request.executable or self.name)
        input_path = request.workdir / "document.typ"
        output_path = request.workdir / "document.pdf"
        typst_source = (
            f"{request.preamble}\n{request.source}"
            if request.preamble
            else request.source
        )
        input_path.write_text(typst_source, encoding="utf-8")
        argv = (
            executable,
            "compile",
            "--diagnostic-format=short",
            *request.extra_args,
            str(input_path),
            str(output_path),
        )
        completed = run_process(
            argv,
            cwd=request.workdir,
            timeout=request.timeout,
            error_type=CompilationError,
        )
        if not output_path.is_file():
            raise CompilationError(
                "compiler reported success but did not create document.pdf",
                argv=argv,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return CompilationResult(
            path=output_path,
            format="pdf",
            engine=self.name,
            argv=argv,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def compiler_from_name(engine: str) -> Compiler:
    """Construct a built-in compiler by public engine name."""
    if engine == "typst":
        return TypstCompiler()
    return TeXCompiler(engine)


def tex_body(source: str, math_mode: bool) -> str:
    """Return the body compiled by TeX and stored for TexText re-editing."""
    if math_mode:
        return f"\\(\\displaystyle {source}\\)"
    return source


def _tex_document(source: str, preamble: str, math_mode: bool) -> str:
    document_class = (
        "" if _contains_document_class(preamble) else "\\documentclass{article}\n"
    )
    return (
        document_class + f"{preamble}\n"
        "\\pagestyle{empty}\n"
        "\\begin{document}\n"
        f"{tex_body(source, math_mode)}\n"
        "\\end{document}\n"
    )


def _contains_document_class(preamble: str) -> bool:
    for line in preamble.splitlines():
        code = line.split("%", maxsplit=1)[0]
        if "\\documentclass{" in code or "\\documentclass[" in code:
            return True
    return False


def normalize_args(args: Sequence[str], *, option: str) -> tuple[str, ...]:
    """Validate subprocess arguments without accepting command strings."""
    if isinstance(args, (str, bytes)):
        raise ConfigurationError(f"{option} must be a sequence of argument strings")
    normalized = tuple(args)
    if not all(isinstance(arg, str) and "\x00" not in arg for arg in normalized):
        raise ConfigurationError(f"{option} must contain only NUL-free strings")
    return normalized
