# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The `vectex` CLI renders a TeX document body to stdout as an SVG `<g>`
  fragment, or writes a standalone SVG through `--output PATH` (also
  `--as-doc`). It provides `--help`, `--version`, and options for the engine,
  math mode, preamble, size, scale, timeout, and ID prefix.
- `render_math()` for bare expressions, and `RenderItem` as a single record for
  everything that shapes a fragment. `render()` accepts one, and
  `render_many()` groups items that share a compilation, so a batch keeps one
  invocation when only sizes or modes differ and splits when a preamble,
  engine, or converter does.
- `VectexFragment.to_svg_document()` and `write_svg_document()` for a
  standalone, backend-free SVG document; `to_svg()` remains the raw `<g>`
  fragment.
- `refresh=True` on `render()` and `render_many()` to recompile and replace one
  cache record without clearing the rest.
- Cache keys that identify the installed tools, so records compiled before a
  TeX or dvisvgm upgrade are not served afterwards. Components may declare an
  `identity()` of their own.
- A placement recipe in the fragments guide covering anchors and baselines.
- MIT licensing for the project and Python distribution.
- User documentation built with Zensical.
- Cropped TeX fragments with derived baselines and direct `size_pt` sizing.
- Deterministic SVG namespaces with an opt-in unique-ID mode.
- Checksummed persistent caching and one-process `render_many` batches.
- Automatic AMS math handling, including `split`, and inherited label colour.

### Changed

- `math_mode` now defaults to `"body"`: source is a TeX document body, as in
  TexText, so `$...$` marks mathematics and prose stays upright. Bare
  expressions need `render_math()` or an explicit mode, and forgetting the
  dollar signs raises a compilation error instead of silently setting words in
  math italic. The earlier `"raw"` spelling of the body mode and the boolean
  spellings `True` and `False` were removed; pass an explicit mode string.
