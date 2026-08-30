from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vectex import (
    CompilationError,
    CompilationResult,
    CompileRequest,
    ConfigurationError,
    ConversionError,
    ConvertRequest,
    DvisvgmConverter,
    MissingExecutableError,
    TeXCompiler,
)
from vectex.compiler import _is_box_compatible_body, _tex_document_many
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
            preamble="\\documentclass{article}\n\\usepackage{amsmath}",
            extra_args=("--extra",),
        )
    )
    assert result.path == tmp_path / "document.pdf"
    assert seen[0][0] == "/bin/pdflatex"
    assert "-no-shell-escape" in seen[0]
    assert "--extra" in seen[0]
    assert seen[0][-1].endswith("document.tex")
    tex = (tmp_path / "document.tex").read_text()
    assert "\\vectexmeasure{0}{x^2}" in tex


def test_default_document_crops_and_explicit_class_wins() -> None:
    default = _tex_document_many(("x",), "")
    explicit = _tex_document_many(("x",), r"\documentclass{article}")
    assert r"\documentclass[border=0pt]{standalone}" in default
    assert r"\usepackage{amsmath}" in default
    assert r"\begin{preview}" in default
    assert explicit.startswith(r"\documentclass{article}")
    assert r"\usepackage{amsmath}" not in explicit
    assert r"\begin{preview}" not in explicit


def test_partial_preamble_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="documentclass"):
        _tex_document_many(("x",), r"\usepackage{bm}")


def test_explicit_full_page_does_not_report_a_box_relative_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "vectex.compiler.find_executable", lambda _tool, _exe: "/bin/pdflatex"
    )

    def fake_run(argv, **_kwargs):
        (tmp_path / "document.pdf").write_bytes(b"pdf")
        (tmp_path / "document.vectex-metrics").write_text("0,4,1\n")
        return completed(tuple(argv))

    monkeypatch.setattr("vectex.compiler.run_process", fake_run)
    result = TeXCompiler("pdflatex").compile(
        CompileRequest(
            source="x",
            workdir=tmp_path,
            timeout=1,
            preamble=r"\documentclass{article}",
        )
    )
    assert result.baseline_ratios == (None,)


@pytest.mark.parametrize(
    "source",
    ["text $x$", r"\(x\)", r"$\begin{pmatrix}a&b\end{pmatrix}$"],
)
def test_inline_tex_bodies_are_box_compatible(source: str) -> None:
    assert _is_box_compatible_body(source)
    document = _tex_document_many((source,), "")
    assert f"\\vectexmeasure{{0}}{{{source}}}" in document


@pytest.mark.parametrize(
    "source",
    [
        "$$x$$",
        r"\[x\]",
        r"\begin{align*}a&=b\end{align*}",
        "first paragraph\n\nsecond paragraph",
        r"first\par second",
    ],
)
def test_display_and_vertical_tex_bodies_are_not_boxed(source: str) -> None:
    assert not _is_box_compatible_body(source)
    document = _tex_document_many((source,), "")
    assert "\\vectexmeasure{0}" not in document


@pytest.mark.parametrize(
    "source",
    [r"\begin{align*}a&=b\end{align*}"],
)
def test_display_math_uses_a_tight_local_paragraph(source: str) -> None:
    document = _tex_document_many((source,), "")
    assert r"\hsize=0pt\displaywidth=0pt" in document


@pytest.mark.parametrize(
    ("source", "tight"),
    [("$$x$$", r"\(\displaystyle x\)"), (r"\[x\]", r"\(\displaystyle x\)")],
)
def test_outer_display_delimiters_use_tight_equivalent_framing(
    source: str, tight: str
) -> None:
    document = _tex_document_many((source,), "")
    assert tight in document


def test_vertical_prose_does_not_use_a_zero_width_paragraph() -> None:
    document = _tex_document_many(("first paragraph\n\nsecond paragraph",), "")
    assert r"\hsize=0pt\displaywidth=0pt" not in document


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
