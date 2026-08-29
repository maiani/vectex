# vectex

`vectex` compiles LaTeX expressions or Typst source and returns one portable SVG
`<g>` fragment. It is a library-level reimplementation of the rendering and
normalization boundary behind TexText: it does not require Inkscape or access to
the destination SVG document.

The returned group is also recognizable as an editable TexText object after a
caller inserts it into an Inkscape SVG. Vectex stores both TexText-compatible
attributes and a richer, versioned metadata record.

## Install

The required runtime is Python 3.10 or newer plus `lxml`:

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

## Minimal use

```python
import vectex

fragment = vectex.render(
    r"E = mc^2",
    engine="pdflatex",
)

svg_text = fragment.to_svg()
lxml_group = fragment.to_lxml()

print(fragment.width, fragment.height, fragment.view_box)
print(fragment.source, fragment.engine, fragment.metadata)
```

By default, LaTeX input is treated as a math expression and compiled as
`\(\displaystyle ...\)`. Set `math_mode=False` when `source` is already a
complete TeX document-body fragment such as an `align` environment. Typst source
is passed through without this wrapper.

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

For the default `math_mode=True`, TexText's `text` field contains the compilable
`\(\displaystyle ...\)` wrapper. The original input remains unchanged in
`fragment.source` and Vectex's namespaced `<metadata>` child. This distinction
lets a simple input such as `E = mc^2` recompile successfully in TexText, whose
compiler otherwise treats its stored source as a complete document body.

TexText represents its preamble as a file path, while Vectex accepts preamble
content. If re-editing must use the same custom preamble, pass both values:

```python
fragment = vectex.render(
    r"\operatorname{rank}(A)",
    preamble=r"\usepackage{amsmath}",
    textext_preamble_file="/absolute/shared/packages.tex",
)
```

The path must remain accessible to TexText on the editing machine. The preamble
content itself is retained in Vectex metadata. Pass `textext_compatible=False`
to omit all TexText attributes.

## Executable discovery and configuration

Built-in components use `shutil.which` to resolve `pdflatex`, `xelatex`,
`lualatex`, `typst`, and `dvisvgm`. Exact overrides make discovery explicit and
testable:

```python
fragment = vectex.render(
    "x+y",
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

## Fragment guarantees

A successful render returns exactly one SVG `<g>` root with:

- copied converter definitions and visible elements;
- a unique per-fragment ID prefix and rewritten `href`, `xlink:href`, and
  `url(#...)` references, including inline style attributes;
- the source viewport represented by an inner matrix transform;
- normalized width, height, view box, scale, and optional baseline properties;
- deterministic repeated serialization of that fragment;
- a Vectex `<metadata>` child containing format version, original source,
  engine, converter, geometry, preamble/options, and adapter-independent data;
- TexText-recognized edit attributes unless explicitly disabled.

The default ID namespace is random so two renderings of the same expression can
be embedded together safely. Supply a valid `id_prefix` for reproducible output
across separate render calls.

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

`recipe/recipe.yaml` provides a noarch Conda recipe for `rattler-build`. A public
release still needs the author to choose a license and set canonical project
URLs/maintainers; those policy choices are intentionally not guessed here.

## Current limitations

- dvisvgm is the only built-in converter and PDF is the only intermediate.
- Baseline extraction is exposed but not yet derived by the built-in drivers.
- Document stylesheets, embedded raster resources, animation, and external
  resources are rejected instead of partially interpreted.
- Vectex does not implement CSS cascading or node-by-node backend translation.
- TexText interoperability is covered at its metadata/detection contract. A
  live Inkscape/TexText GUI round trip remains an optional system-level check.
- Destination-document insertion, placement, replacement, GUI behavior, and
  Inkscape selection management belong to the caller.
