from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vectex import (
    CompilationError,
    CompilationResult,
    CompileRequest,
    ConversionError,
    ConvertRequest,
    DvisvgmConverter,
    MissingExecutableError,
    TeXCompiler,
    TypstCompiler,
)
from vectex.process import find_executable, run_process


def completed(argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, 0, "standard output", "diagnostics")


def test_tex_compiler_constructs_safe_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "vectex.compiler.find_executable", lambda _tool, _exe: "/bin/pdflatex"
    )

    def fake_run(argv, **kwargs):
        seen.append(tuple(argv))
        (tmp_path / "document.pdf").write_bytes(b"pdf")
        assert kwargs["cwd"] == tmp_path
        assert kwargs["timeout"] == 7
        return completed(tuple(argv))

    monkeypatch.setattr("vectex.compiler.run_process", fake_run)
    result = TeXCompiler("pdflatex").compile(
        CompileRequest(
            source="x^2",
            workdir=tmp_path,
            timeout=7,
            preamble="\\usepackage{amsmath}",
            extra_args=("--extra",),
        )
    )
    assert result.path == tmp_path / "document.pdf"
    assert seen[0][0] == "/bin/pdflatex"
    assert "-no-shell-escape" in seen[0]
    assert "--extra" in seen[0]
    assert seen[0][-1].endswith("document.tex")
    tex = (tmp_path / "document.tex").read_text()
    assert "\\(\\displaystyle x^2\\)" in tex


def test_typst_compiler_constructs_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "vectex.compiler.find_executable", lambda _tool, _exe: "/bin/typst"
    )

    def fake_run(argv, **_kwargs):
        (tmp_path / "document.pdf").write_bytes(b"pdf")
        return completed(tuple(argv))

    monkeypatch.setattr("vectex.compiler.run_process", fake_run)
    result = TypstCompiler().compile(
        CompileRequest(
            source="$x$", workdir=tmp_path, timeout=3, preamble="#set text(size: 12pt)"
        )
    )
    assert result.argv[:3] == ("/bin/typst", "compile", "--diagnostic-format=short")
    assert (tmp_path / "document.typ").read_text().startswith("#set text")


def test_dvisvgm_constructs_safe_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pdf = tmp_path / "document.pdf"
    pdf.write_bytes(b"pdf")
    compiled = CompilationResult(pdf, "pdf", "pdflatex", (), "", "")
    monkeypatch.setattr(
        "vectex.converter.find_executable", lambda _tool, _exe: "/bin/dvisvgm"
    )

    def fake_run(argv, **_kwargs):
        (tmp_path / "document.svg").write_text('<svg viewBox="0 0 1 1"/>')
        return completed(tuple(argv))

    monkeypatch.setattr("vectex.converter.run_process", fake_run)
    result = DvisvgmConverter().convert(
        ConvertRequest(compiled, tmp_path, 4, ("--precision=5",))
    )
    assert result.argv[0] == "/bin/dvisvgm"
    assert "--pdf" in result.argv
    assert "--no-fonts" in result.argv
    assert "--precision=5" in result.argv


def test_missing_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    with pytest.raises(MissingExecutableError) as error:
        find_executable("pdflatex", "missing-pdflatex")
    assert error.value.tool == "pdflatex"
    assert error.value.executable == "missing-pdflatex"


def test_nonzero_process_error_contains_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["tool"], 2, "stdout detail", "stderr detail"
        ),
    )
    with pytest.raises(CompilationError) as error:
        run_process(
            ["tool", "input"], cwd=tmp_path, timeout=1, error_type=CompilationError
        )
    assert error.value.returncode == 2
    assert error.value.argv == ("tool", "input")
    assert error.value.stderr == "stderr detail"
    assert "stderr detail" in str(error.value)


def test_timeout_is_structured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["tool"], 2, output=b"partial", stderr=b"late")

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ConversionError) as error:
        run_process(["tool"], cwd=tmp_path, timeout=2, error_type=ConversionError)
    assert error.value.timed_out
    assert error.value.stdout == "partial"
    assert "timed out" in str(error.value)
