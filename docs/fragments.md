# Fragments

`vectex.render()` returns an immutable `VectexFragment`. It preserves a
canonical normalized SVG serialization while providing safe copies for callers.

```python
fragment = vectex.render(r"$\int_0^1 x\,dx$")

svg_text = fragment.to_svg()
group = fragment.to_lxml()
metadata = fragment.metadata
```

The public fields are `source`, `engine`, `converter`, `scale`, `width`,
`height`, `view_box`, and `baseline`. Built-in TeX rendering derives the
baseline from measured box height and depth; it is expressed downward from the
fragment's top edge and scales with the fragment.

## Placing a fragment

`width`, `height`, and `baseline` are the whole placement interface: the
fragment origin is its cropped top-left corner, so an anchor becomes an offset
and a wrapper transform. A caller that draws labels usually wants this once:

```python
def label(drawing, x, y, source, *, anchor="middle", valign="baseline"):
    """Place a label with (x, y) on one edge of its box."""
    fragment = vectex.render(source, size_pt=7, cache_dir=".cache")
    dx = {"start": 0.0, "middle": -fragment.width / 2, "end": -fragment.width}[anchor]
    dy = {
        "top": 0.0,
        "middle": -fragment.height / 2,
        "bottom": -fragment.height,
        "baseline": -fragment.baseline,
    }[valign]
    group = drawsvg.Group(transform=f"translate({x + dx},{y + dy})")
    group.append(fragment.to_drawsvg())
    drawing.append(group)
```

Prefer baseline alignment when labels must read as one line: a word with a
descender aligned by the bottom of its box sits optically higher than a word
without one, because the box, not the type, is what got aligned.

## Serialization and copies

`to_svg()` returns the deterministic canonical serialization. `to_lxml()`
parses and returns a fresh, mutable `lxml` group every time, so appending or
editing the returned element cannot change the original fragment.

When their optional dependencies are installed, `to_svg_py()` and
`to_drawsvg()` return insertable wrappers for `svg.py` and `drawsvg`.

## Portability

Vectex copies only the definitions required by visible SVG content and rewrites
local IDs and references to a deterministic prefix derived from all
output-driving inputs. Identical calls therefore serialize identically. Use
`unique_ids=True` when inserting the same render more than once into one SVG,
or provide `id_prefix` to control the namespace. An explicit prefix passed to
`render_many` receives an input-position suffix.

Default black glyph paths do not override `fill`, so a fill set on a destination
wrapper group recolours the whole label. Explicit non-black source colours are
preserved. The fragment origin is its cropped top-left corner, allowing free
placement through a wrapper transform in `svg.py`, drawsvg, or raw SVG.

The metadata record contains the original source, render engine and converter,
geometry, options, and format version. It supplements TexText-compatible
attributes on the outer group rather than replacing them.

TexText can preserve only a preamble *file path* in its compatibility
attributes. Vectex preserves the actual `preamble` content in its own metadata;
pass `textext_preamble_file` as well when later TexText editing must load those
same packages or definitions.
