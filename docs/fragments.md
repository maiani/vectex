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
`height`, `view_box`, and `baseline`. For box-compatible inline and prose TeX,
the baseline is derived from measured height and depth; it is expressed
downward from the fragment's top edge and scales with the fragment. Display and
other vertical TeX bodies have `baseline=None` unless the caller supplies one
explicitly.

## Placing a fragment

`width`, `height`, and the optional `baseline` are the whole placement
interface: the fragment origin is its cropped top-left corner. They are in TeX
points, the unit of the geometry; `width_px`, `height_px`, and `baseline_px`
give the same in CSS px, the user unit of svg.py and drawsvg documents, which is
what `to_svg_py()` and `to_drawsvg()` produce.

Those two wrappers can also place the label for you. `x` and `y`, in the
wrapper's unit, are where one point of its box goes: `anchor` names it across
(`"start"`, `"middle"`, `"end"`) and `valign` down (`"top"`, `"middle"`,
`"bottom"`, `"baseline"`). By default the top-left corner goes to the origin,
as before:

```python
label = vectex.render(r"$E = mc^2$", size_pt=9)
drawing.append(label.to_drawsvg(x=40, y=120, anchor="middle", valign="baseline"))
svg_py_elements.append(label.to_svg_py(x=40, y=120, valign="baseline"))
```

`valign="baseline"` needs a measured baseline and raises `ConfigurationError`
for a fragment without one, such as display maths; pass `baseline=` when
rendering it, or align it by its box. Placement is one translation on the
wrapper, so the canonical group inside is unchanged.

Prefer baseline alignment when labels must read as one line: a word with a
descender aligned by the bottom of its box sits optically higher than a word
without one, because the box, not the type, is what got aligned.

## Integration boundary

VecTeX creates a normalized fragment and reports its geometry, and its wrappers
can offset the label by that geometry. The caller owns insertion into a
destination document, layout, replacement, GUI behavior, and Inkscape
selection management. The returned outer group should remain
intact when TexText compatibility is needed.

## Serialization and copies

`to_svg()` returns the deterministic canonical serialization. `to_lxml()`
parses and returns a fresh, mutable `lxml` group every time, so appending or
editing the returned element cannot change the original fragment.
`to_svg_document()` wraps the group in a complete standalone SVG document (XML
header, `<svg>` root, `width`, `height`, and `viewBox`) that can be opened or
served directly, and `write_svg_document(path)` writes that same document to a
file; neither needs an object-model backend.

The same two forms are available from the command line: `vectex '$E = mc^2$'`
prints the fragment, while `vectex '$E = mc^2$' --as-doc` prints a standalone
document. `-o PATH` writes the selected form to a file, so
`vectex '$E = mc^2$' --as-doc -o einstein.svg` writes a standalone document
and `vectex '$E = mc^2$' -o label.svg` writes the fragment.
Use `--input PATH` for UTF-8 source files or the positional `-` to read source
from standard input.

When their optional dependencies are installed, `to_svg_py()` and
`to_drawsvg()` return insertable wrappers for `svg.py` and `drawsvg`. Both
documents measure in CSS px, so by default the wrappers scale the label from TeX
points to px (96/72) and it keeps its size: an 8 pt label is 8 pt there too, and
`width_px` by `height_px`. `unit="pt"` gives the canonical group unscaled. Two
`svg.py` wrappers are equal exactly when they hold the same markup, so a
document built from them compares and deduplicates as plain `svg.py` would.

## Portability

VecTeX copies only the definitions required by visible SVG content, in the
order that content first uses them whatever order the converter wrote, and
rewrites local IDs and references to a deterministic prefix derived from all
output-driving inputs. Identical calls therefore serialize identically. Use
`unique_ids=True` when inserting the same render more than once into one SVG,
or provide `id_prefix` to control the namespace. An explicit prefix passed to
`render_many` receives an input-position suffix.

The prefix also names the outer group: `id_prefix="einstein"` produces
`id="einstein-root"`. The CLI accepts the same value through
`--id-prefix einstein`.

The fragment origin is its cropped top-left corner, allowing free placement
through a wrapper transform in `svg.py`, drawsvg, or raw SVG.

## Colour

TeX draws in black by default, and VecTeX makes that black follow the CSS
colour instead: the outer group's fill and every default-black fill and stroke
are `currentColor`. A label is therefore black wherever nothing sets a colour,
and takes the `color` of the element it is placed in -- glyphs and rules alike,
so a fraction bar or a radical's rule recolours with the symbols around it:

```python
purple = vectex.render(r"$\frac{\mu}{2}$", color="#7a1fa2")  # baked in
plain = vectex.render(r"$\frac{\mu}{2}$")  # follows where it is placed:
# <g color="#7a1fa2"> ... plain ... </g>
```

`color=` takes one CSS colour and sets it on the outer group, so the fragment
carries it everywhere it goes; `RenderItem(color=...)` colours one label of a
batch, and the CLI takes `--color`. Colour does not affect compilation, so a
batch of labels in different colours is still one TeX run.

Parts coloured in the TeX source keep their colour: with
`extra_packages=("xcolor",)`, `\color{red}` or `\textcolor[HTML]{1F5FA8}{...}`
paints exactly what it covers, rules included, and the rest follows the label's
colour. Set colour with `color`, not `fill`: the label's own `currentColor`
fill takes precedence over a `fill` on the group around it.

The metadata record contains the original source, render engine and converter,
geometry, options, and format version. It supplements TexText-compatible
attributes on the outer group rather than replacing them.

TexText can preserve only a preamble *file path* in its compatibility
attributes. VecTeX preserves the actual `preamble` content in its own metadata;
pass `textext_preamble_file` as well when later TexText editing must load those
same packages or definitions.
