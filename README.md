# vectex

[![Test](https://github.com/maiani/vectex/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/maiani/vectex/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/vectex.svg)](https://pypi.org/project/vectex/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-3DA639)](LICENSE)

`vectex` compiles LaTeX expressions or Typst source and returns one portable SVG
`<g>` fragment. It is a library-level reimplementation of the rendering and
normalization boundary behind TexText: it does not require Inkscape or access to
the destination SVG document.

The returned group is also recognizable as an editable TexText object after a
caller inserts it into an Inkscape SVG. Vectex stores both TexText-compatible
attributes and a richer, versioned metadata record.

## Install

The required runtime is Python 3.10 or newer; installation includes `lxml` and
the command-line dependency `typer`:

```console
python -m pip install vectex
```

Install an optional object-model adapter with one of:

```console
python -m pip install 'vectex[svg-py]'
python -m pip install 'vectex[drawsvg]'
python -m pip install 'vectex[all]'
```

The distribution names and imports are `svg.py` / `import svg` and `drawsvg` /
`import drawsvg`.

## Command line

The installed `vectex` command renders a TeX document body to a portable SVG
fragment on standard output:

```console
vectex '$E = mc^2$'
```

Pass `--as-doc` to emit a complete, openable SVG document rather than a
fragment. Without `-o`, either form is written to standard output:

```console
vectex '$E = mc^2$' --as-doc > einstein.svg
```

Use `--output` (or `-o`) to write the selected form to a file:

```console
vectex '$E = mc^2$' -o einstein-fragment.svg
vectex '$E = mc^2$' --as-doc -o einstein.svg
```

Use `--executable NAME=PATH` to override a tool location; repeat it for both
the engine and `dvisvgm` when needed. Run `vectex --help` for the complete
option list; `vectex --version` reports the installed version.

## Minimal use

```python
import vectex

fragment = vectex.render(
    r"mass $m$ and energy $E = mc^2$",
    engine="pdflatex",
)
expression = vectex.render(r"$E = mc^2$")

svg_text = fragment.to_svg()
lxml_group = fragment.to_lxml()
document = fragment.to_svg_document()  # complete file-ready SVG
fragment.write_svg_document("label.svg")  # same document, written to disk

print(fragment.width, fragment.height, fragment.view_box)
print(fragment.source, fragment.engine, fragment.metadata)
```

TeX input is always a literal document body, the same convention TexText uses:
`$...$` marks inline mathematics, `\[...\]` marks display mathematics, and
everything else is prose. Complete environments such as `align*` can be used
directly; inner environments need their normal TeX context. `amsmath` is loaded
by default, so `\text{...}` works in math expressions. Typst source is passed
through unchanged.

The default TeX template uses a zero-border `standalone` page cropped to each
fragment. A `\documentclass` supplied in `preamble` takes precedence, so an
explicit `\documentclass{article}` restores full-page geometry.

Use either `size_pt=7` to express a desired font size or the lower-level
`scale=0.7`; passing both is an error. TeX sizing is resolved against the
selected document class (10 pt by default), while Typst uses its 11 pt default.

Every call uses a fresh temporary directory and runs two stages:

```text
source -> pdflatex/xelatex/lualatex/typst -> PDF -> dvisvgm -> SVG -> lxml -> <g>
```

## Embedding and adapters

`to_lxml()` returns a fresh element on every call, so appending or editing it
cannot mutate the fragment's canonical serialization:

```python
from lxml import etree

document = etree.fromstring('<svg xmlns="http://www.w3.org/2000/svg"/>')
document.append(fragment.to_lxml())
```

The optional adapters deliberately preserve the complete normalized XML rather
than translating arbitrary SVG into a smaller object model:

```python
import svg
import drawsvg

svg_py_group = fragment.to_svg_py()
svg_py_document = svg.SVG(
    width=fragment.width,
    height=fragment.height,
    elements=[svg_py_group],
)

drawing = drawsvg.Drawing(fragment.width, fragment.height)
drawing.append(fragment.to_drawsvg())
```

## TexText editing in Inkscape

TexText detects editable nodes from attributes in its namespace on the selected
outer `<g>`. Vectex emits the current compatibility fields: encoded source,
compiler, PDF-to-SVG converter marker, preamble-file path, scale, alignment,
version, and transform Jacobian.

Insert the outer group itself into an SVG and select that whole group before
opening TexText. Selecting only a nested path or subgroup is intentionally
rejected by TexText.

The stored TexText `text` is the source itself, since both tools treat it as a
document body. The same `$...$`, `\[...\]`, and environment syntax therefore
recompiles without translation when the object is edited in TexText.

TexText represents its preamble as a file path, while Vectex accepts preamble
content. If re-editing must use the same custom preamble, pass both values:

```python
fragment = vectex.render(
    r"$\operatorname{rank}(A)$",
    preamble=r"\usepackage{amsmath}",
    textext_preamble_file="/absolute/shared/packages.tex",
)
```

The path must remain accessible to TexText on the editing machine. The preamble
content itself is retained in Vectex metadata, but TexText's compatibility field
can carry only its path. Pass `textext_compatible=False` to omit all TexText
attributes.

## Executable discovery and configuration

Built-in components use `shutil.which` to resolve `pdflatex`, `xelatex`,
`lualatex`, `typst`, and `dvisvgm`. Exact overrides make discovery explicit and
testable:

```python
fragment = vectex.render(
    "$x+y$",
    executable_overrides={
        "pdflatex": "/opt/texlive/bin/pdflatex",
        "dvisvgm": "/opt/texlive/bin/dvisvgm",
    },
    timeout=20,
    compiler_args=("--synctex=0",),
    converter_args=("--precision=6",),
)
```

Argument options are sequences, never shell command strings. Vectex never uses
`shell=True`. Nonzero exits and timeouts raise structured `CompilationError` or
`ConversionError` instances with argv, return code, stdout, and stderr.

Applications may implement the small `Compiler` and `Converter` protocols and
pass component objects instead of built-in names.

## Batch rendering and disk cache

`render_many([a, b, ...])` shares one compiler and one dvisvgm invocation while
preserving each expression's crop and measurable baseline. A source may also be
a `RenderItem` carrying any option that shapes its fragment; those left as
`None` take the batch value. Items that share a compilation are grouped and
rendered together, so a batch of labels differing only in size still costs one
invocation, while an item with its own preamble or engine forms its own group.
Fragments are returned in input order, and `render()` accepts a `RenderItem`
as well. `cache_dir`, `refresh`, and `unique_ids` describe how a call runs
rather than what it produces, and stay on the call.

The optional persistent cache is enabled with `cache_dir=` or
`VECTEX_CACHE_DIR`. Entries are keyed by all output-driving options and by the
identity of the installed tools -- built-in components contribute the resolved
path and reported version of their executable, so records are not reused across
a TeX or dvisvgm upgrade, and a component object may declare its own
`identity()`. Entries are checksummed and written atomically; corrupt entries
are treated as misses. `refresh=True` recompiles and replaces one record, and
`vectex.clear_cache(directory)` removes only Vectex's namespaced records and
returns the number removed.

## Fragment guarantees

A successful render returns exactly one SVG `<g>` root with:

- copied converter definitions and visible elements;
- a deterministic input-derived ID prefix and rewritten `href`, `xlink:href`, and
  `url(#...)` references, including inline style attributes;
- the source viewport represented by an inner matrix transform;
- normalized width, height, view box, scale, and measurable baseline properties;
- inheritable default black glyph fills, so `fill` on an enclosing SVG group
  recolours a label, while explicitly authored non-black colours are preserved;
- deterministic repeated serialization of that fragment;
- a Vectex `<metadata>` child containing format version, original source,
  engine, converter, geometry, preamble/options, and adapter-independent data;
- TexText-recognized edit attributes unless explicitly disabled.

Identical render inputs serialize identically, while changed output-driving
inputs receive a different namespace. Use `unique_ids=True` when embedding the
same render more than once in one SVG, or supply an explicit `id_prefix`.
`render_many(..., id_prefix="labels")` suffixes it by input position.

The outer group is named from that prefix: `id_prefix="einstein"` gives
`id="einstein-root"`, while rewritten definitions use IDs such as
`einstein-0`. The CLI exposes this as `--id-prefix einstein`.

## Security and trust assumptions

The XML parser disables DTD loading, entity resolution, network access, recovery,
comments, and processing instructions. Normalization rejects scripts,
`foreignObject`, SVG animation, event handlers, document CSS `<style>` elements,
CSS imports, external hrefs/URLs, duplicate IDs, and unresolved local references.
This conservative policy avoids active content and dependencies on destination
document CSS.

LaTeX and Typst are powerful programs, not safe sandboxes. Vectex passes
`-no-shell-escape` to built-in TeX engines, but a malicious source or trusted
extra compiler option can still read files or consume resources according to the
compiler's capabilities. Only compile trusted source, and use an OS/container
sandbox when processing untrusted input. Executable overrides, preamble content,
and extra argv values are trusted application configuration.

## Development and packaging

Unit tests use checked-in SVG fixtures and mocked subprocesses; they need no TeX
installation:

```console
uv sync --all-extras
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run python -m build
```

Run optional real-tool tests only when explicitly requested:

```console
VECTEX_RUN_INTEGRATION=1 uv run pytest -m integration
```

Vectex is distributed under the MIT License.

## Scope

Vectex produces static, self-contained SVG fragments; it does not manipulate a
destination SVG document. See [Rendering](docs/rendering.md) for the
built-in pipeline, Typst baseline behavior, TexText contract, and trust policy,
and [Fragments](docs/fragments.md) for placement and caller integration.
