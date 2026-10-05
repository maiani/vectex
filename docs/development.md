# Development

Install the complete development environment with:

```console
uv sync --all-extras
```

Run the standard checks before submitting a change:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy src examples
uv run pytest
uv run python -m build
```

Unit tests use checked-in SVG fixtures and mocked subprocesses, so they do not
require TeX or dvisvgm. To request the optional real-tool integration
tests, run:

```console
VECTEX_RUN_INTEGRATION=1 uv run pytest -m integration
```

The routine CI matrix runs unit tests on Python 3.12 and 3.14 on Linux, and
once each on macOS and Windows. A separate job installs a real TeX Live and
runs the integration tests on pushes, on releases, and nightly, but not on
pull requests, where the TeX download would dominate the run.

## Examples

`examples/` holds runnable scripts that are the realistic end-to-end check:
they drive TeX and dvisvgm the way a caller does, and they render pictures
whose correctness is visible.

```console
uv run python examples/bloch_sphere.py --theta 50 --phi 40
uv run python examples/figure_labels.py --cache-dir .cache/vectex
```

Each writes into `examples/out/`, which is ignored by git, and `--output-dir`
sends the output elsewhere. `uv sync --all-extras` adds `cairosvg`, which the
`--png` flag needs; the package itself never rasterizes.

They are also tests. `tests/test_examples.py` runs every script in `examples/`
and calls the `build()` each one exposes, gated behind
`VECTEX_RUN_INTEGRATION=1` like the other real-tool tests. Two consequences
worth knowing:

* An example that stops working fails the suite, so the documented code cannot
  rot silently.
* A new example is picked up automatically by the glob. Give it a `build()`
  returning a fragment or a sequence of them, and a `--output-dir` option.

## Documentation

The documentation source lives in `docs/`, with site configuration in
`zensical.toml`. Build it locally with:

```console
uv run zensical build
```

For a live preview, use `uv run zensical serve`. The generated `site/`
directory is ignored by Git. Keep relevant documentation, examples, and this
reference synchronized with public behavior changes.

## Publishing to PyPI

The `Test` workflow runs for every push and pull request and can also be run
manually. Publishing is triggered by a `v*` tag push, such as `v0.1.0`, or by
manual dispatch with an existing tag specified. It first verifies that the tag
is exactly `v` plus `[project].version` in `pyproject.toml`, then calls the same
test workflow against that tag as a required gate. Only after that succeeds does
it build, metadata-check, and upload the wheel and source distribution.
The test workflow uses the checked-in `uv.lock`, so CI and the documented local
environment resolve the same dependencies.

It uses PyPI Trusted Publishing rather than a stored API token. Before the
first release, configure a PyPI trusted publisher for the `vectex` project with
GitHub owner `maiani`, repository `vectex`, workflow `publish.yml`, and
environment `pypi`. The GitHub `pypi` environment can then require a reviewer
before publishing. Ensure the release tag corresponds to the version in
`pyproject.toml`.
