"""Command-line rendering interface."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .api import render
from .exceptions import VectexError


def _print_version(value: bool) -> None:
    """Print the package version before Click validates required arguments."""
    if value:
        typer.echo(f"vectex {__version__}")
        raise typer.Exit()


def _executable_overrides(values: Sequence[str]) -> dict[str, str]:
    """Parse repeated ``NAME=PATH`` command-line options."""
    overrides: dict[str, str] = {}
    for value in values:
        name, separator, executable = value.partition("=")
        if not separator or not name or not executable:
            raise typer.BadParameter("must have the form NAME=PATH")
        if "\x00" in name or "\x00" in executable:
            raise typer.BadParameter("must not contain NUL characters")
        if name in overrides:
            raise typer.BadParameter(f"sets {name!r} more than once")
        overrides[name] = executable
    return overrides


def _read_text(path: Path, label: str) -> str:
    """Read one UTF-8 CLI input and report a concise parameter error."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise typer.BadParameter(f"cannot read {label} {str(path)!r}: {exc}") from exc


def _source_text(source: str | None, input_path: Path | None) -> str:
    """Resolve literal, file, or standard-input source."""
    if source is not None and input_path is not None:
        raise typer.BadParameter("SOURCE and --input are alternatives")
    if input_path is not None:
        return _read_text(input_path, "input file")
    if source == "-":
        return sys.stdin.read()
    if source is None:
        raise typer.BadParameter("provide SOURCE, SOURCE=-, or --input PATH")
    return source


def _preamble_text(preamble: str, preamble_file: Path | None) -> tuple[str, str]:
    """Resolve preamble content and its TexText-compatible file path."""
    if preamble and preamble_file is not None:
        raise typer.BadParameter("--preamble and --preamble-file are alternatives")
    if preamble_file is None:
        return preamble, ""
    return _read_text(preamble_file, "preamble file"), str(preamble_file.resolve())


app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Render LaTeX source as a portable SVG fragment.",
    no_args_is_help=True,
)


@app.command()
def main(
    source: Annotated[
        str | None,
        typer.Argument(help="TeX source to render, or '-' to read standard input."),
    ] = None,
    input_path: Annotated[
        Path | None,
        typer.Option(
            "--input",
            "-i",
            help="Read TeX source from a UTF-8 file instead of SOURCE.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the selected SVG form to PATH instead of standard output.",
        ),
    ] = None,
    as_doc: Annotated[
        bool,
        typer.Option(
            "--as-doc",
            help="Output a standalone SVG document instead of an SVG <g> fragment.",
        ),
    ] = False,
    engine: Annotated[
        str,
        typer.Option("--engine", help="Rendering engine to invoke."),
    ] = "pdflatex",
    preamble: Annotated[
        str,
        typer.Option(
            "--preamble",
            help=(
                "Complete TeX preamble containing \\documentclass; "
                "alternative to --extra-package."
            ),
        ),
    ] = "",
    preamble_file: Annotated[
        Path | None,
        typer.Option(
            "--preamble-file",
            help="Read a complete TeX preamble from a UTF-8 file.",
        ),
    ] = None,
    extra_package: Annotated[
        list[str] | None,
        typer.Option(
            "--extra-package",
            help=(
                "Load a TeX package by name; repeat for more packages; "
                "alternative to a custom preamble."
            ),
        ),
    ] = None,
    size_pt: Annotated[
        float | None,
        typer.Option("--size-pt", help="Desired font size in points."),
    ] = None,
    scale: Annotated[
        float | None,
        typer.Option("--scale", help="Scale the rendered fragment."),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Maximum compiler time in seconds."),
    ] = 30.0,
    id_prefix: Annotated[
        str | None,
        typer.Option(
            "--id-prefix",
            help="Prefix for the outer group and all rewritten SVG IDs.",
        ),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option(
            "--cache-dir",
            help="Reuse checksummed render records from this directory.",
        ),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Recompile and replace this render's cache record.",
        ),
    ] = False,
    executable: Annotated[
        list[str] | None,
        typer.Option(
            "--executable",
            help="Override an executable with NAME=PATH; repeat for more tools.",
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Show Vectex's version and exit.",
        ),
    ] = False,
) -> None:
    """Render SOURCE and emit an SVG fragment or standalone SVG file."""
    del version
    source_text = _source_text(source, input_path)
    preamble_text, textext_preamble_file = _preamble_text(preamble, preamble_file)
    executable_overrides = _executable_overrides(executable or ())
    try:
        fragment = render(
            source_text,
            engine=engine,
            preamble=preamble_text,
            extra_packages=tuple(extra_package or ()),
            size_pt=size_pt,
            scale=scale,
            timeout=timeout,
            id_prefix=id_prefix,
            cache_dir=cache_dir,
            refresh=refresh,
            textext_preamble_file=textext_preamble_file,
            executable_overrides=executable_overrides or None,
        )
    except VectexError as exc:
        raise typer.BadParameter(str(exc)) from exc
    serialized = fragment.to_svg_document() if as_doc else fragment.to_svg()
    if output is None:
        typer.echo(serialized, nl=not serialized.endswith("\n"))
    else:
        output.write_text(serialized, encoding="utf-8")
