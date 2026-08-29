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


class BatchCompiler(FakeCompiler):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def compile(self, request):
        self.calls += 1
        result = super().compile(request)
        return CompilationResult(
            result.path,
            result.format,
            result.engine,
            result.argv,
            result.stdout,
            result.stderr,
            (0.75,),
        )

    def compile_many(self, requests):
        self.calls += 1
        self.workdir = requests[0].workdir
        path = self.workdir / "fake.pdf"
        path.write_bytes(b"pdf")
        return CompilationResult(
            path,
            "pdf",
            self.name,
            ("fake-tex",),
            "",
            "",
            (0.75,) * len(requests),
            len(requests),
        )


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


class BatchConverter(FakeConverter):
    def __init__(self, svg: bytes) -> None:
        super().__init__(svg)
        self.calls = 0

    def convert(self, request):
        self.calls += 1
        return super().convert(request)

    def convert_many(self, request):
        self.calls += 1
        results = []
        for page in range(request.compiled.page_count):
            path = request.workdir / f"fake-{page}.svg"
            path.write_bytes(self.svg)
            results.append(ConversionResult(path, self.name, ("fake-svg",), "", ""))
        return tuple(results)


def test_render_vertical_slice_and_temp_cleanup(simple_svg: bytes) -> None:
    compiler = FakeCompiler()
    converter = FakeConverter(simple_svg)
    fragment = vectex.render(
        "E = mc^2",
        engine=compiler,
        converter=converter,
        math_mode="inline",
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


def test_default_ids_are_deterministic_and_unique_ids_are_available(
    simple_svg: bytes,
) -> None:
    compiler = FakeCompiler()
    converter = FakeConverter(simple_svg)
    first = vectex.render("x", engine=compiler, converter=converter)
    second = vectex.render("x", engine=compiler, converter=converter)
    other = vectex.render("y", engine=compiler, converter=converter)
    unique = vectex.render("x", engine=compiler, converter=converter, unique_ids=True)
    assert first.to_svg() == second.to_svg()
    assert first.to_lxml().get("id") != other.to_lxml().get("id")
    assert first.to_lxml().get("id") != unique.to_lxml().get("id")


def test_size_pt_and_scale_are_alternatives(simple_svg: bytes) -> None:
    fragment = vectex.render(
        "x", engine=FakeCompiler(), converter=FakeConverter(simple_svg), size_pt=7
    )
    assert fragment.scale == 0.7
    assert fragment.width == 7
    class_sized = vectex.render(
        "x",
        engine=FakeCompiler(),
        converter=FakeConverter(simple_svg),
        preamble=r"\documentclass [12pt] {article}",
        size_pt=6,
    )
    assert class_sized.scale == 0.5
    with pytest.raises(vectex.ConfigurationError, match="alternatives"):
        vectex.render(
            "x",
            engine=FakeCompiler(),
            converter=FakeConverter(simple_svg),
            scale=1,
            size_pt=7,
        )


def test_render_many_uses_one_batch_invocation_and_derives_baseline(
    simple_svg: bytes,
) -> None:
    compiler = BatchCompiler()
    converter = BatchConverter(simple_svg)
    fragments = vectex.render_many(
        ["x", "g"], engine=compiler, converter=converter, id_prefix="batch"
    )
    assert compiler.calls == 1
    assert converter.calls == 1
    assert [fragment.baseline for fragment in fragments] == [3.0, 3.0]
    assert [fragment.to_lxml().get("id") for fragment in fragments] == [
        "batch-0-root",
        "batch-1-root",
    ]


def test_disk_cache_detects_corruption_and_can_be_cleared(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, simple_svg: bytes
) -> None:
    compiler = BatchCompiler()
    converter = BatchConverter(simple_svg)
    monkeypatch.setattr("vectex.api.compiler_from_name", lambda _name: compiler)
    monkeypatch.setattr("vectex.api.converter_from_name", lambda _name: converter)
    first = vectex.render("x", cache_dir=tmp_path)
    second = vectex.render("x", cache_dir=tmp_path)
    assert first.to_svg() == second.to_svg()
    assert compiler.calls == 1
    record = next((tmp_path / "vectex-v1").glob("*.json"))
    record.write_text("partial", encoding="utf-8")
    vectex.render("x", cache_dir=tmp_path)
    assert compiler.calls == 2
    assert vectex.clear_cache(tmp_path) == 1


class IdentifiedCompiler(BatchCompiler):
    """A compiler that reports its own identity, as installed tools do."""

    def __init__(self, identity: str = "fake-tex-1") -> None:
        super().__init__()
        self.reported = identity

    def identity(self) -> str:
        return self.reported


class IdentifiedConverter(BatchConverter):
    def identity(self) -> str:
        return "fake-converter-1"


def test_default_math_mode_is_the_document_body(simple_svg: bytes) -> None:
    compiler = FakeCompiler()
    fragment = vectex.render(
        "x^2", engine=compiler, converter=FakeConverter(simple_svg)
    )
    assert compiler.request.math_mode == "body"
    assert "\\\\(\\\\displaystyle" not in fragment.to_svg()


def test_raw_is_accepted_as_the_body_mode(simple_svg: bytes) -> None:
    compiler = FakeCompiler()
    vectex.render(
        "x^2", engine=compiler, converter=FakeConverter(simple_svg), math_mode="raw"
    )
    assert compiler.request.math_mode == "body"


@pytest.mark.parametrize("display, expected", [(False, "inline"), (True, "display")])
def test_render_math_sets_the_mode(
    simple_svg: bytes, display: bool, expected: str
) -> None:
    compiler = FakeCompiler()
    vectex.render_math(
        "x^2",
        engine=compiler,
        converter=FakeConverter(simple_svg),
        display=display,
    )
    assert compiler.request.math_mode == expected


def test_render_math_rejects_an_explicit_mode(simple_svg: bytes) -> None:
    with pytest.raises(vectex.ConfigurationError, match="math_mode"):
        vectex.render_math(
            "x",
            engine=FakeCompiler(),
            converter=FakeConverter(simple_svg),
            math_mode="body",
        )


def test_render_many_accepts_per_item_overrides(simple_svg: bytes) -> None:
    compiler = BatchCompiler()
    converter = BatchConverter(simple_svg)
    small, large = vectex.render_many(
        [
            vectex.RenderItem("x", size_pt=5),
            vectex.RenderItem("y", size_pt=10, math_mode="inline"),
        ],
        engine=compiler,
        converter=converter,
        size_pt=20,
    )
    assert compiler.calls == 1
    assert small.scale == 0.5
    assert large.scale == 1.0
    assert large.width == 2 * small.width


def test_cache_records_track_the_toolchain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, simple_svg: bytes
) -> None:
    compiler = IdentifiedCompiler()
    converter = IdentifiedConverter(simple_svg)
    monkeypatch.setattr("vectex.api.compiler_from_name", lambda _name: compiler)
    monkeypatch.setattr("vectex.api.converter_from_name", lambda _name: converter)
    vectex.render("x", cache_dir=tmp_path)
    vectex.render("x", cache_dir=tmp_path)
    assert compiler.calls == 1
    compiler.reported = "fake-tex-2"  # the installation changed under the cache
    vectex.render("x", cache_dir=tmp_path)
    assert compiler.calls == 2
    assert len(list((tmp_path / "vectex-v1").glob("*.json"))) == 2


def test_refresh_recompiles_and_replaces_the_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, simple_svg: bytes
) -> None:
    compiler = IdentifiedCompiler()
    converter = IdentifiedConverter(simple_svg)
    monkeypatch.setattr("vectex.api.compiler_from_name", lambda _name: compiler)
    monkeypatch.setattr("vectex.api.converter_from_name", lambda _name: converter)
    vectex.render("x", cache_dir=tmp_path)
    vectex.render("x", cache_dir=tmp_path, refresh=True)
    assert compiler.calls == 2
    assert len(list((tmp_path / "vectex-v1").glob("*.json"))) == 1


def test_render_accepts_a_render_item(simple_svg: bytes) -> None:
    compiler = FakeCompiler()
    fragment = vectex.render(
        vectex.RenderItem("x", size_pt=5, math_mode="inline"),
        engine=compiler,
        converter=FakeConverter(simple_svg),
        size_pt=20,
    )
    assert compiler.request.math_mode == "inline"
    assert fragment.scale == 0.5


def test_render_many_groups_by_compilation_and_keeps_order(simple_svg: bytes) -> None:
    shared = BatchCompiler()
    private = BatchCompiler()
    converter = BatchConverter(simple_svg)
    first, second, third = vectex.render_many(
        [
            "x",
            vectex.RenderItem("y", preamble="\\usepackage{amssymb}"),
            vectex.RenderItem("z", engine=private),
        ],
        engine=shared,
        converter=converter,
    )
    # One group per distinct compilation: two on the shared engine, one on its own.
    assert shared.calls == 2
    assert private.calls == 1
    assert [first.source, second.source, third.source] == ["x", "y", "z"]


def test_render_many_shares_one_run_for_size_only_differences(
    simple_svg: bytes,
) -> None:
    compiler = BatchCompiler()
    converter = BatchConverter(simple_svg)
    fragments = vectex.render_many(
        [
            vectex.RenderItem("x", size_pt=5),
            vectex.RenderItem("y", size_pt=10),
            vectex.RenderItem("z", math_mode="inline"),
        ],
        engine=compiler,
        converter=converter,
    )
    assert compiler.calls == 1
    assert converter.calls == 1
    assert [fragment.scale for fragment in fragments] == [0.5, 1.0, 1.0]
