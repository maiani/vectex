# Vectex

Vectex compiles LaTeX expressions or Typst source into a self-contained,
editable SVG `<g>` fragment. It provides the rendering and normalization
boundary behind TexText without requiring Inkscape or access to a destination
SVG document.

The returned outer group remains recognizable by TexText after a caller inserts
it into an Inkscape SVG. Vectex also records versioned metadata that is useful
to applications that manage their own editing workflow.

## Install

Vectex requires Python 3.10 or newer and installs with `lxml`:

```console
python -m pip install vectex
```

Optional adapters are available as extras:

```console
python -m pip install 'vectex[svg-py]'
python -m pip install 'vectex[drawsvg]'
python -m pip install 'vectex[all]'
```

`svg.py` is imported as `svg`; `drawsvg` is imported as `drawsvg`.

## Quick start

```python
import vectex

fragment = vectex.render(r"$E = mc^2$", engine="pdflatex")

print(fragment.width, fragment.height, fragment.view_box)
svg_group = fragment.to_svg()
```

The standard pipeline is:

```text
source -> TeX or Typst -> PDF -> dvisvgm -> SVG -> normalized <g>
```

Built-in components discover their executables from `PATH`. For normal use,
install a supported TeX engine or Typst plus `dvisvgm`; see [Rendering](rendering.md)
for explicit executable paths and other configuration.

## Guarantees

On success, Vectex returns one normalized SVG group with local IDs rewritten,
unsafe SVG features rejected, and independent copies available to callers. See
[Fragments](fragments.md) for the full object contract.

## License

Vectex is distributed under the [MIT License](https://opensource.org/license/mit).
