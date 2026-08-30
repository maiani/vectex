# Vectex contributor guide

## Scope

`vectex` compiles LaTeX and normalizes converter output into one
self-contained SVG `<g>` fragment. It does not insert fragments into destination
documents, implement an SVG editor, or provide a GUI.

## Architecture

- Keep a single canonical `lxml` pipeline: compiler -> converter -> normalizer
  -> `VectexFragment` -> optional adapters.
- Keep external process execution in `compiler.py` and `converter.py`; never use
  `shell=True`.
- Keep SVG trust-boundary checks and ID/reference rewriting in `normalizer.py`.
- Preserve TexText interoperability on the outer group. Its namespaced `text`,
  `preamble`, and `scale` attributes are a compatibility contract in addition
  to Vectex's canonical `<metadata>` record.
- Treat the serialized normalized group owned by `VectexFragment` as immutable.
  Return copies or new wrapper objects from public conversion methods.
- Preserve optional dependency boundaries. Import `svg.py` (`import svg`) and
  `drawsvg` only inside their adapters.
- Before 1.0, make API changes directly: update consumers, tests, and docs, and
  do not add compatibility aliases, deprecated wrappers, or legacy option shims.

## Development

- Supported Python: 3.11 and newer.
- Install a complete development environment with `uv sync --all-extras`.
- Run `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy src`, and `uv run pytest` before reporting a change complete.
- Unit tests must not require TeX or dvisvgm. Real-tool integration
  tests must be explicitly enabled and skip cleanly when tools are absent.
- Add a regression fixture or mocked-process test for every normalization,
  security, or command-construction bug.
- Keep `docs/` in sync with user-visible code changes: update affected guides,
  reference material, and examples in the same change. Build the site with
  `uv run zensical build` before reporting documentation changes complete.
- Keep `CHANGELOG.md` current for notable user-facing changes. Follow the
  Keep a Changelog 1.1.0 format: add concise, human-readable entries under
  `Unreleased`, grouped only as Added, Changed, Deprecated, Removed, Fixed, or
  Security; move them into a dated release section when a version is released.

## Packaging and releases

- `pyproject.toml` is canonical for Python metadata and pip builds.
- Build both wheel and sdist for package qualification.
- Do not commit, tag, upload, or publish unless the user explicitly requests it.
- The project is distributed under the MIT License; keep the license metadata
  and `LICENSE` file in sync for public releases.

Keep maintained behavior and examples in `README.md` and `docs/`; completed
planning notes are not part of the long-lived project documentation.
