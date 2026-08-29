from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import vectex
from vectex.cli import app
from vectex.exceptions import MissingExecutableError
from vectex.normalizer import Normalizer

runner = CliRunner()


def test_cli_prints_a_fragment(monkeypatch, simple_svg: bytes) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    monkeypatch.setattr("vectex.cli.render", lambda source, **kwargs: fragment)

    result = runner.invoke(app, ["$E=mc^2$"])

    assert result.exit_code == 0
    assert result.stdout == f"{fragment.to_svg()}\n"


def test_cli_prints_a_standalone_document(monkeypatch, simple_svg: bytes) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    monkeypatch.setattr("vectex.cli.render", lambda source, **kwargs: fragment)

    result = runner.invoke(app, ["$E=mc^2$", "--as-doc"])

    assert result.exit_code == 0
    assert result.stdout == fragment.to_svg_document()


def test_cli_writes_a_standalone_document(
    monkeypatch, tmp_path: Path, simple_svg: bytes
) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    monkeypatch.setattr("vectex.cli.render", lambda source, **kwargs: fragment)
    target = tmp_path / "einstein.svg"

    result = runner.invoke(app, ["$E=mc^2$", "--as-doc", "-o", str(target)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert target.read_text(encoding="utf-8") == fragment.to_svg_document()


def test_cli_output_writes_a_fragment(
    monkeypatch, tmp_path: Path, simple_svg: bytes
) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    monkeypatch.setattr("vectex.cli.render", lambda source, **kwargs: fragment)
    target = tmp_path / "einstein.svg"

    result = runner.invoke(app, ["$E=mc^2$", "-o", str(target)])

    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == fragment.to_svg()


def test_cli_version_and_help() -> None:
    version = runner.invoke(app, ["--version"])
    help_result = runner.invoke(app, ["--help"], env={"COLUMNS": "120"})

    assert version.exit_code == 0
    assert version.stdout == f"vectex {vectex.__version__}\n"
    assert help_result.exit_code == 0
    assert "--as-doc" in help_result.stdout
    assert "--output" in help_result.stdout
    assert "--id-prefix" in help_result.stdout
    assert "--engine" in help_result.stdout
    assert "--math-mode" not in help_result.stdout
    assert "--executable" in help_result.stdout
    assert "--version" in help_result.stdout


def test_cli_forwards_rendering_options(monkeypatch, simple_svg: bytes) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    received: dict[str, object] = {}

    def fake_render(source: str, **kwargs: object):
        received["source"] = source
        received.update(kwargs)
        return fragment

    monkeypatch.setattr("vectex.cli.render", fake_render)

    result = runner.invoke(
        app,
        [
            "$E=mc^2$",
            "--engine",
            "xelatex",
            "--preamble",
            r"\usepackage{amsmath}",
            "--size-pt",
            "7",
            "--timeout",
            "10",
            "--id-prefix",
            "einstein",
            "--executable",
            "xelatex=/opt/texlive/bin/xelatex",
            "--executable",
            "dvisvgm=/opt/texlive/bin/dvisvgm",
        ],
    )

    assert result.exit_code == 0
    assert received == {
        "source": "$E=mc^2$",
        "engine": "xelatex",
        "preamble": r"\usepackage{amsmath}",
        "size_pt": 7.0,
        "scale": None,
        "timeout": 10.0,
        "id_prefix": "einstein",
        "executable_overrides": {
            "xelatex": "/opt/texlive/bin/xelatex",
            "dvisvgm": "/opt/texlive/bin/dvisvgm",
        },
    }


@pytest.mark.parametrize(
    "value, message",
    [
        ("pdflatex", "NAME=PATH"),
        ("=pdflatex", "NAME=PATH"),
        ("pdflatex=", "NAME=PATH"),
    ],
)
def test_cli_rejects_malformed_executable_override(value: str, message: str) -> None:
    result = runner.invoke(app, ["$E=mc^2$", "--executable", value])

    assert result.exit_code != 0
    assert message in result.output


def test_cli_rejects_duplicate_executable_override() -> None:
    result = runner.invoke(
        app,
        [
            "$E=mc^2$",
            "--executable",
            "pdflatex=/one/pdflatex",
            "--executable",
            "pdflatex=/two/pdflatex",
        ],
    )

    assert result.exit_code != 0
    assert "sets 'pdflatex' more than once" in result.output


def test_cli_reports_missing_rendering_tool(monkeypatch) -> None:
    def missing_tool(source: str, **kwargs: object) -> None:
        del source, kwargs
        raise MissingExecutableError("pdflatex", "pdflatex")

    monkeypatch.setattr("vectex.cli.render", missing_tool)

    result = runner.invoke(app, ["$E=mc^2$"])

    assert result.exit_code != 0
    assert "Cannot find the 'pdflatex' executable 'pdflatex' on PATH" in result.output
