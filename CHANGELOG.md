# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
