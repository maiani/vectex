# Vectex

Vectex compiles LaTeX source into a self-contained,
editable SVG `<g>` fragment. It provides the rendering and normalization
boundary behind TexText without requiring Inkscape or access to a destination
SVG document.

The returned outer group remains recognizable by TexText after a caller inserts
it into an Inkscape SVG. Vectex also records versioned metadata that is useful
to applications that manage their own editing workflow.

## Related projects

`vectex` is developed alongside [FigForge](https://github.com/maiani/figforge),
which composes multi-panel figures, and
[vecview](https://github.com/maiani/vecview), which draws layered 3D schematics
as SVG. The three form a suite for publication figures, and each is usable on its
own.

`vectex` depends on neither. A composition layer needs only `to_svg_document()`,
so the integration costs no import in either direction.

## Install

Vectex requires Python 3.11 or newer and installs with `lxml` and Typer:

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
source -> TeX -> PDF -> dvisvgm -> SVG -> normalized <g>
```

Built-in components discover their executables from `PATH`. For normal use,
install a supported TeX engine plus `dvisvgm`; see [Rendering](rendering.md)
for explicit executable paths and other configuration.

## Guarantees

On success, Vectex returns one normalized SVG group with local IDs rewritten,
unsafe SVG features rejected, and independent copies available to callers. See
[Fragments](fragments.md) for the full object contract.

## License

Vectex is distributed under the [MIT License](https://opensource.org/license/mit).
