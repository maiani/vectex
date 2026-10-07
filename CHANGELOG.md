# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `color=` on `render`, `render_many`, and `RenderItem`, and `--color` on the
  command line: one CSS colour for the whole label, glyphs and rules alike,
  set on the outer group.  Parts coloured in the TeX source keep theirs, and a
  batch in several colours is still one compilation.
- `width_px`, `height_px`, and `baseline_px`: the fragment's geometry in CSS
  px, the user unit of svg.py and drawsvg documents.

### Changed

- TeX's default black, in fills and strokes, is now `currentColor`, and the
  outer group's fill is too: a label takes the CSS `color` of where it is
  placed, its fraction bars and radicals included, which used to stay black.
  Recolour with `color`, not `fill`: the label's own fill now takes precedence
  over a `fill` on an enclosing group.
- `to_svg_py()` and `to_drawsvg()` scale the label from TeX points to CSS px by
  default, so it keeps its size in a px document instead of drawing at three
  quarters of it; `unit="pt"` keeps the canonical group.
- Disk cache records written by an earlier version are misses, since the same
  options now produce a different fragment.
- Use ty for type checking in development and CI instead of mypy.

### Fixed

- `render_many` with pdflatex placed every label without depth after the first
  -- `$x$`, `$2\Delta$` -- shifted left by the previous label's width, partly
  outside its own crop.  pdfTeX positions the first glyph of a page whose
  baseline lies on the bottom edge from where the previous page's text ended;
  the crop now reaches a thousandth of a point below such a baseline, and the
  baseline stays exact.  Fragments from a batch are again identical to
  individual renders.
- `to_svg_py()` wrappers compare by their markup. Each call used to define a
  new wrapper class, so two wrappers of the same fragment were never equal,
  while two wrappers from one class were equal whatever they held.

## [0.2.1] - 2026-10-05

### Changed

- Prose spells the project VecTeX; the distribution, import, and command names
  stay `vectex`. The sibling projects are now FigWorks (formerly FigForge) and
  VecWire (formerly cirquit).

## [0.2.0] - 2026-10-05

### Added

- A `py.typed` marker, so the annotations VecTeX already checks internally now
  reach consumers. Without it every downstream `import vectex` resolved to
  `Any`, silently voiding type checking against this package.
- Continuous integration against a real TeX toolchain. The `integration` job
  installs TeX Live, verifies that `pdflatex`, `xelatex`, `lualatex`, and
  `dvisvgm` are all present — the tests skip themselves when one is missing, so
  an unchecked install would report a green, empty run — and then runs the
  integration suite. It runs on pushes, on releases, and nightly, but not on
  pull requests, where installing TeX would dominate the run.
- Unit tests on macOS and Windows, covering the platform-dependent halves of
  executable lookup and path handling.
- A documented stability policy and platform support matrix in the README and
  the documentation: what the public API is, what may still change before 1.0,
  and which platforms continuous integration actually exercises.
- An `examples/` directory that doubles as an end-to-end test suite.
  `bloch_sphere.py` renders a TikZ Bloch sphere from a full preamble;
  `figure_labels.py` renders a batch of maths labels in one compilation and
  demonstrates the persistent cache. Each exposes a `build()` and an
  `--output-dir`, and `tests/test_examples.py` globs the directory and runs
  every script, so a new example needs no registration and a broken one fails
  the suite. The integration CI job renders them and uploads the pictures as
  build artifacts.
- A TikZ section in the rendering guide and the README, including that
  `extra_packages` cannot express `\usetikzlibrary` and that `dvisvgm`
  silently drops PDF shadings.

### Changed

- **Python 3.12 is now the floor**, raised from 3.11, matching the sibling
  projects. Ruff and mypy target 3.12 accordingly, and `run_process` uses PEP
  695 type-parameter syntax.
- The package is classified `Development Status :: 4 - Beta`, and declares the
  operating systems continuous integration covers.

### Fixed

- `to_svg_document()` declares its `width` and `height` in `pt`. Fragment
  geometry is in TeX points, but the unitless lengths read as CSS px, so any
  consumer honouring the document's size drew labels at 3/4 of their size.
- Surrounding whitespace in a source no longer changes what is rendered. A
  trailing newline — which every triple-quoted Python string has — became a
  paragraph break inside the tight local paragraph used for environment
  bodies, silently producing a full US Letter page instead of a cropped
  fragment; on an inline body it widened the measured box by one space.

## [0.1.0] - 2026-08-30

### Added

- The `vectex` CLI renders a TeX document body to stdout as an SVG `<g>`
  fragment; `--as-doc` selects a standalone SVG document, and `--output PATH`
  writes either selected form to a file. It provides `--help`, `--version`, and
  options for file or standard-input source, inline or file-backed preambles,
  the render cache, engine, size, scale, timeout, ID prefix, and repeatable
  `--executable NAME=PATH` tool overrides.
- `RenderItem` as a single record for everything that shapes a fragment.
  `render()` accepts one, and `render_many()` groups items that share a
  compilation, so a batch keeps one invocation when only sizes differ and
  splits when a preamble, engine, or converter does.
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
- Cropped TeX fragments with measured inline baselines and direct `size_pt`
  sizing.
- Safe package-name convenience through `extra_packages=(...)` and repeatable
  CLI `--extra-package NAME`, without requiring a custom preamble. A nonempty
  `preamble` is the complete preamble, must contain `\documentclass`, and is
  mutually exclusive with `extra_packages`.
- Deterministic SVG namespaces with an opt-in unique-ID mode.
- Checksummed persistent caching and one-process `render_many` batches.
- Inherited label colour for easy styling after insertion.
- Support for Python 3.11 and newer.
- One canonical package version shared by `vectex.__version__`, the CLI, and
  `pyproject.toml` metadata.
- Literal TeX document-body input, as in TexText, using normal delimiters and
  environments without automatic math wrapping.
