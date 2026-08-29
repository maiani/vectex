# Development

Install the complete development environment with:

```console
uv sync --all-extras
```

Run the standard checks before submitting a change:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run python -m build
```

Unit tests use checked-in SVG fixtures and mocked subprocesses, so they do not
require TeX, Typst, or dvisvgm. To request the optional real-tool integration
tests, run:

```console
VECTEX_RUN_INTEGRATION=1 uv run pytest -m integration
```

## Documentation

The documentation source lives in `docs/`, with site configuration in
`zensical.toml`. Build it locally with:

```console
uv run zensical build
```

For a live preview, use `uv run zensical serve`. The generated `site/`
directory is ignored by Git. Keep relevant documentation, examples, and this
reference synchronized with public behavior changes.
