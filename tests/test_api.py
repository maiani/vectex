from __future__ import annotations

from pathlib import Path

import pytest

import vectex
from vectex import CompilationResult, ConversionResult


class FakeCompiler:
    name = "pdflatex"

    def __init__(self) -> None:
        self.workdir: Path | None = None
        self.request = None

    def compile(self, request):
        self.workdir = request.workdir
        self.request = request
        path = request.workdir / "fake.pdf"
        path.write_bytes(b"pdf")
        return CompilationResult(path, "pdf", self.name, ("fake-tex",), "", "")


class FakeConverter:
    name = "dvisvgm"

    def __init__(self, svg: bytes) -> None:
        self.svg = svg
        self.request = None

    def convert(self, request):
        self.request = request
        path = request.workdir / "fake.svg"
        path.write_bytes(self.svg)
        return ConversionResult(path, self.name, ("fake-svg",), "", "")


def test_render_vertical_slice_and_temp_cleanup(simple_svg: bytes) -> None:
    compiler = FakeCompiler()
    converter = FakeConverter(simple_svg)
    fragment = vectex.render(
        "E = mc^2",
        engine=compiler,
        converter=converter,
        scale=1.5,
        timeout=9,
        preamble="\\usepackage{amsmath}",
        compiler_args=("--trusted",),
        converter_args=("--exact",),
        id_prefix="api",
        textext_preamble_file="/opt/vectex/preamble.tex",
    )
    assert fragment.source == "E = mc^2"
    assert fragment.width == 15
    assert compiler.request.timeout == 9
    assert compiler.request.extra_args == ("--trusted",)
    assert converter.request.extra_args == ("--exact",)
    assert compiler.workdir is not None
    assert not compiler.workdir.exists()
    assert "\\\\(\\\\displaystyle E = mc^2\\\\)" in fragment.to_svg()


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"source": ""}, "source"),
        ({"source": "x", "timeout": 0}, "timeout"),
        ({"source": "x", "compiler_args": "--bad"}, "compiler_args"),
        ({"source": "x", "textext_alignment": ""}, "alignment"),
    ],
)
def test_render_rejects_bad_options(
    simple_svg: bytes, kwargs: dict, message: str
) -> None:
    compiler = FakeCompiler()
    converter = FakeConverter(simple_svg)
    with pytest.raises(vectex.ConfigurationError, match=message):
        vectex.render(engine=compiler, converter=converter, **kwargs)
