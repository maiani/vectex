"""Command-line rendering interface."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from . import __version__
from .api import render
from .compiler import MathMode
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


app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Render LaTeX or Typst source as a portable SVG fragment.",
    no_args_is_help=True,
)


@app.command()
def main(
    source: Annotated[
        str,
        typer.Argument(help="TeX document body or Typst source to render."),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            "--as-doc",
            help=(
                "Write a standalone SVG document instead of printing its <g> fragment."
            ),
        ),
    ] = None,
    engine: Annotated[
        str,
        typer.Option("--engine", help="Rendering engine to invoke."),
    ] = "pdflatex",
    math_mode: Annotated[
        MathMode,
        typer.Option(
            "--math-mode",
            help="Interpret source as a TeX body, inline or display math, or infer it.",
        ),
    ] = "body",
    preamble: Annotated[
        str,
        typer.Option("--preamble", help="TeX preamble additions."),
    ] = "",
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
    executable_overrides = _executable_overrides(executable or ())
    try:
        fragment = render(
            source,
            engine=engine,
            math_mode=math_mode,
            preamble=preamble,
            size_pt=size_pt,
            scale=scale,
            timeout=timeout,
            id_prefix=id_prefix,
            executable_overrides=executable_overrides or None,
        )
    except VectexError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if output is None:
        typer.echo(fragment.to_svg())
    else:
        fragment.write_svg_document(output)
