from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

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


def test_cli_reads_source_from_standard_input(monkeypatch, simple_svg: bytes) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    received: dict[str, object] = {}

    def fake_render(source: str, **kwargs: object):
        received["source"] = source
        return fragment

    monkeypatch.setattr("vectex.cli.render", fake_render)

    result = runner.invoke(app, ["-"], input="$E=mc^2$\n")

    assert result.exit_code == 0
    assert received["source"] == "$E=mc^2$\n"


def test_cli_reads_source_from_file(
    monkeypatch, tmp_path: Path, simple_svg: bytes
) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$E=mc^2$", engine="pdflatex", converter="dvisvgm"
    )
    source_path = tmp_path / "equation.tex"
    source_path.write_text("$E=mc^2$\n", encoding="utf-8")
    received: dict[str, object] = {}

    def fake_render(source: str, **kwargs: object):
        received["source"] = source
        return fragment

    monkeypatch.setattr("vectex.cli.render", fake_render)

    result = runner.invoke(app, ["--input", str(source_path)])

    assert result.exit_code == 0
    assert received["source"] == "$E=mc^2$\n"


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
            "--extra-package",
            "bm",
            "--extra-package",
            "siunitx",
            "--size-pt",
            "7",
            "--timeout",
            "10",
            "--id-prefix",
            "einstein",
            "--cache-dir",
            ".vectex-cache",
            "--refresh",
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
        "preamble": "",
        "extra_packages": ("bm", "siunitx"),
        "size_pt": 7.0,
        "scale": None,
        "timeout": 10.0,
        "id_prefix": "einstein",
        "cache_dir": Path(".vectex-cache"),
        "refresh": True,
        "textext_preamble_file": "",
        "executable_overrides": {
            "xelatex": "/opt/texlive/bin/xelatex",
            "dvisvgm": "/opt/texlive/bin/dvisvgm",
        },
    }


def test_cli_reads_preamble_file_and_records_its_path(
    monkeypatch, tmp_path: Path, simple_svg: bytes
) -> None:
    fragment = Normalizer().normalize(
        simple_svg, source="$x$", engine="pdflatex", converter="dvisvgm"
    )
    preamble_path = tmp_path / "preamble.tex"
    preamble_path.write_text(
        "\\documentclass{standalone}\n\\usepackage{bm}", encoding="utf-8"
    )
    received: dict[str, object] = {}

    def fake_render(source: str, **kwargs: object):
        received.update(kwargs)
        return fragment

    monkeypatch.setattr("vectex.cli.render", fake_render)

    result = runner.invoke(app, ["$x$", "--preamble-file", str(preamble_path)])

    assert result.exit_code == 0
    assert received["preamble"] == "\\documentclass{standalone}\n\\usepackage{bm}"
    assert received["textext_preamble_file"] == str(preamble_path.resolve())


@pytest.mark.parametrize(
    "arguments, message",
    [
        (["literal", "--input", "source.tex"], "alternatives"),
        (["literal", "--preamble", "x", "--preamble-file", "p.tex"], "alternatives"),
        (
            [
                "literal",
                "--preamble",
                r"\documentclass{standalone}",
                "--extra-package",
                "bm",
            ],
            "alternatives",
        ),
    ],
)
def test_cli_rejects_ambiguous_text_inputs(arguments: list[str], message: str) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code != 0
    assert message in result.output


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
