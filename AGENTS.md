# Vectex contributor guide

## Scope

`vectex` compiles LaTeX or Typst and normalizes converter output into one
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

## Development

- Supported Python: 3.10 and newer.
- Install a complete development environment with `uv sync --all-extras`.
- Run `uv run ruff format --check .`, `uv run ruff check .`,
  `uv run mypy src`, and `uv run pytest` before reporting a change complete.
- Unit tests must not require TeX, Typst, or dvisvgm. Real-tool integration
  tests must be explicitly enabled and skip cleanly when tools are absent.
- Add a regression fixture or mocked-process test for every normalization,
  security, or command-construction bug.

## Packaging and releases

- `pyproject.toml` is canonical for Python metadata and pip builds.
- Keep `recipe/recipe.yaml` version and dependencies aligned with
  `pyproject.toml`.
- Build both wheel and sdist for package qualification. Build the Conda recipe
  when `conda-build` or a compatible builder is available.
- Do not commit, tag, upload, or publish unless the user explicitly requests it.
- A public release still requires the author to choose and add a license.

## Plan

The complete initial implementation plan and acceptance criteria are maintained
in `PLAN.md`. Update it when scope or completion status changes.
