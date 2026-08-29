"""Compiler interfaces and built-in TeX/Typst implementations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .exceptions import CompilationError, ConfigurationError
from .process import find_executable, run_process

_DOCUMENT_CLASS_RE = re.compile(r"\\documentclass\s*(?:\[([^]]*)\]\s*)?\{([^}]+)\}")


@dataclass(frozen=True, slots=True)
class CompileRequest:
    """Inputs shared by compiler implementations."""

    source: str
    workdir: Path
    timeout: float
    preamble: str = ""
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
    baseline_ratios: tuple[float | None, ...] = ()
    page_count: int = 1


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
        return self.compile_many((request,))

    def compile_many(self, requests: Sequence[CompileRequest]) -> CompilationResult:
        """Compile multiple expressions as separate PDF pages in one process."""
        if not requests:
            raise ConfigurationError("compile_many requires at least one request")
        request = requests[0]
        _validate_batch_requests(requests)
        executable = find_executable(self.name, request.executable or self.name)
        input_path = request.workdir / "document.tex"
        output_path = request.workdir / "document.pdf"
        input_path.write_text(
            _tex_document_many(
                tuple(item.source for item in requests),
                request.preamble,
            ),
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
        ratios = _read_baseline_ratios(
            request.workdir / "document.vectex-metrics", len(requests)
        )
        if not _uses_cropped_pages(request.preamble):
            ratios = (None,) * len(requests)
        return CompilationResult(
            path=output_path,
            format="pdf",
            engine=self.name,
            argv=argv,
            stdout=completed.stdout,
            stderr=completed.stderr,
            baseline_ratios=ratios,
            page_count=len(requests),
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


def _tex_document(source: str, preamble: str) -> str:
    """Build a single-expression document (kept for tests and extensions)."""
    return _tex_document_many((source,), preamble)


def _tex_document_many(
    sources: Sequence[str],
    preamble: str,
) -> str:
    explicit_class = _contains_document_class(preamble)
    cropped = _uses_cropped_pages(preamble)
    if explicit_class:
        header = f"{preamble}\n\\usepackage{{amsmath}}\n"
    else:
        header = (
            "\\documentclass[border=0pt]{standalone}\n"
            "\\usepackage{amsmath}\n"
            f"{preamble}\n"
        )
    if cropped:
        header += (
            "\\usepackage[active,tightpage]{preview}\n\\setlength\\PreviewBorder{0pt}\n"
        )
    pages = []
    for index, source in enumerate(sources):
        content = _measured_tex_body(index, source)
        if not cropped:
            if index:
                pages.append("\\newpage\n")
            pages.append(content)
        else:
            pages.append(f"\\begin{{preview}}\n{content}\n\\end{{preview}}\n")
    return (
        header + _METRICS_PREAMBLE + "\\pagestyle{empty}\n"
        "\\begin{document}\n"
        + "".join(pages)
        + "\\immediate\\closeout\\vectexmetrics\n"
        "\\end{document}\n"
    )


_METRICS_PREAMBLE = r"""
\makeatletter
\newwrite\vectexmetrics
\immediate\openout\vectexmetrics=\jobname.vectex-metrics
\newsavebox{\vectexbox}
\newcommand{\vectexmeasure}[2]{%
  \sbox{\vectexbox}{#2}%
  \immediate\write\vectexmetrics{#1,\strip@pt\ht\vectexbox,\strip@pt\dp\vectexbox}%
  \usebox{\vectexbox}%
}
\makeatother
"""


def _measured_tex_body(index: int, source: str) -> str:
    if _is_box_compatible_body(source):
        return f"\\vectexmeasure{{{index}}}{{{source}}}"
    return source


def _is_box_compatible_body(source: str) -> bool:
    """Return whether a literal TeX body is safe to measure in an ``\\sbox``."""
    in_inline_math = False
    index = 0
    while index < len(source):
        if source.startswith("$$", index):
            return False
        character = source[index]
        if character == "\\":
            if source.startswith(r"\[", index):
                return False
            if source.startswith(r"\(", index):
                in_inline_math = True
                index += 2
                continue
            if source.startswith(r"\)", index):
                in_inline_math = False
                index += 2
                continue
            command = re.match(r"\\([A-Za-z@]+|.)", source[index:])
            if command is not None:
                name = command.group(1)
                if not in_inline_math and name in {"begin", "par"}:
                    return False
                index += len(command.group(0))
                continue
        elif character == "$":
            in_inline_math = not in_inline_math
        elif character == "\n" and not in_inline_math:
            if re.match(r"\n[ \t]*\n", source[index:]):
                return False
        index += 1
    return True


def _read_baseline_ratios(path: Path, count: int) -> tuple[float | None, ...]:
    ratios: list[float | None] = [None] * count
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return tuple(ratios)
    for line in lines:
        fields = line.strip().split(",")
        try:
            index = int(fields[0])
        except (IndexError, ValueError):
            continue
        if not 0 <= index < count:
            continue
        try:
            height, depth = float(fields[1]), float(fields[2])
        except (IndexError, ValueError):
            continue
        total = height + depth
        ratios[index] = height / total if total > 0 else None
    return tuple(ratios)


def _validate_batch_requests(requests: Sequence[CompileRequest]) -> None:
    first = requests[0]
    for request in requests[1:]:
        if (
            request.workdir != first.workdir
            or request.timeout != first.timeout
            or request.preamble != first.preamble
            or request.extra_args != first.extra_args
            or request.executable != first.executable
        ):
            raise ConfigurationError("batch compiler requests must share all options")


def _contains_document_class(preamble: str) -> bool:
    return _document_class(preamble) is not None


def _document_class(preamble: str) -> tuple[str, tuple[str, ...]] | None:
    code = "\n".join(line.split("%", maxsplit=1)[0] for line in preamble.splitlines())
    match = _DOCUMENT_CLASS_RE.search(code)
    if match is None:
        return None
    options = tuple(
        option.strip() for option in (match.group(1) or "").split(",") if option.strip()
    )
    return match.group(2).strip(), options


def _uses_cropped_pages(preamble: str) -> bool:
    document_class = _document_class(preamble)
    return document_class is None or document_class[0] == "standalone"


def tex_base_size(preamble: str) -> float:
    """Return the document class's nominal point size, defaulting to 10 pt."""
    document_class = _document_class(preamble)
    if document_class is not None:
        for option in document_class[1]:
            match = re.fullmatch(r"(\d+(?:\.\d+)?)pt", option)
            if match:
                return float(match.group(1))
    return 10.0


def normalize_args(args: Sequence[str], *, option: str) -> tuple[str, ...]:
    """Validate subprocess arguments without accepting command strings."""
    if isinstance(args, (str, bytes)):
        raise ConfigurationError(f"{option} must be a sequence of argument strings")
    normalized = tuple(args)
    if not all(isinstance(arg, str) and "\x00" not in arg for arg in normalized):
        raise ConfigurationError(f"{option} must contain only NUL-free strings")
    return normalized
