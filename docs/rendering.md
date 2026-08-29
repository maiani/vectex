# Rendering

`vectex.render()` compiles source in a fresh temporary directory, converts its
PDF result with dvisvgm, and returns a normalized `VectexFragment`.

```python
import vectex

fragment = vectex.render(
    r"the rank $\operatorname{rank}(A)$",
    engine="pdflatex",
    timeout=20,
)
```

## Engines and converter

Built-in engine names are `pdflatex`, `xelatex`, `lualatex`, and `typst`; the
built-in converter is `dvisvgm`. Applications may instead supply objects that
implement Vectex's public `Compiler` and `Converter` protocols.

To make executable locations explicit, pass a mapping keyed by the component
name:

```python
fragment = vectex.render(
    "x+y",
    executable_overrides={
        "pdflatex": "/opt/texlive/bin/pdflatex",
        "dvisvgm": "/opt/texlive/bin/dvisvgm",
    },
    compiler_args=("--synctex=0",),
    converter_args=("--precision=6",),
)
```

Arguments are sequences, never shell command strings. Vectex does not invoke a
shell. A failed command or timeout raises a structured `CompilationError` or
`ConversionError` containing the command context.

## TeX input

The default `math_mode="body"` treats source as a TeX document body, the same
convention TexText uses: `$...$` marks mathematics and everything else is
prose. A label is therefore written the way it would be written in a paper, and
forgetting the dollar signs around an expression raises a compilation error
rather than silently typesetting words in math italic.

For a bare expression, `render_math()` supplies the wrapper:

```python
label = vectex.render_math(r"\omega_c")
heading = vectex.render_math(r"\sum_i x_i", display=True)
```

Explicit modes are `"inline"`, `"display"`, `"body"`, and `"auto"`; `"raw"` is
accepted as a spelling of `"body"`, and the compatible booleans `True` and
`False` mean inline and body. `amsmath` is loaded automatically, so `\text{...}`
works inside math mode.

`math_mode="auto"` infers a wrapper from the source: it recognizes AMS
environments, adapts inner display environments such as `split` to a
crop-compatible form while their original source remains in metadata and
TexText's editable body, and uses complete environments such as `align`
unwrapped.

```python
fragment = vectex.render(
    r"\begin{split} a &= b \\ c &= d \end{split}",
)
```

TeX uses a zero-border `standalone` document cropped to the content. An explicit
document class in `preamble` wins; `\documentclass{article}` therefore produces
a full page intentionally. Use `size_pt=7` for a semantic font size or
`scale=0.7` for direct geometric scaling. They are alternatives.

## Batches and persistent cache

`render_many()` typesets all requested sources as separately cropped pages in
one compiler process and converts them in one dvisvgm process:

```python
labels = vectex.render_many([r"$\omega_c$", r"$E_{\rm zpf}$", "input"])
```

A source may also be a `RenderItem` carrying its own options; those left as
`None` take the batch value. Items that share a compilation -- the same engine,
converter, preamble, timeout, process arguments, and executable overrides --
are compiled together, and an item that differs simply forms its own group.
Fragments come back in input order:

```python
labels = vectex.render_many(
    [
        vectex.RenderItem(r"$\omega_c$", size_pt=7),
        vectex.RenderItem("altermagnet", size_pt=6),
    ],
    preamble=r"\usepackage{lmodern}",
)
```

`render()` accepts a `RenderItem` too, so one record can describe a label
whether it is rendered alone or as part of a batch. `cache_dir`, `refresh`, and
`unique_ids` describe how a call is executed rather than what it produces, and
stay on the call.

Enable the opt-in disk cache with `cache_dir=".cache"` or the
`VECTEX_CACHE_DIR` environment variable. A second process can reuse a valid
entry without invoking either external tool. Records are checksummed and
atomically replaced; corrupt or partial records become cache misses.

Cache keys cover the source, the options, and the identity of the installed
tools: built-in components report the resolved path and reported version of
their executable, so records compiled before a TeX or dvisvgm upgrade are not
served afterwards. A component object may declare its own `identity()` instead.
Pass `refresh=True` to recompile and replace one record without discarding the
rest, or call `vectex.clear_cache(".cache")` to remove all versioned Vectex
entries.

## TexText compatibility

TexText-compatible attributes are emitted by default. Keep the outer group
intact when inserting the result into an SVG, and select that whole group before
editing in TexText. Pass `textext_compatible=False` to omit these attributes.

`preamble` stores preamble content in Vectex metadata. If a TexText edit must
reuse a shared preamble file, also provide `textext_preamble_file` with a path
that will be available on the editing machine.

## Trust boundary

LaTeX and Typst are not sandboxes. Vectex disables TeX shell escape for its
built-in TeX engines, but trusted source may still read files or consume
resources according to compiler capabilities. Use an OS or container sandbox
when processing untrusted input.

The SVG normalizer rejects scripts, event handlers, external resources,
animation, document stylesheets, unresolved references, and other unsafe or
non-portable constructs.
