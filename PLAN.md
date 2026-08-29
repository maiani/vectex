# Vectex initial implementation plan

## Goal and acceptance boundary

Deliver a coherent Python library that turns a LaTeX expression or Typst source
into one portable, editable SVG `<g>` fragment. The initial production vertical
slice must invoke real external compilers and dvisvgm, while the normal test
suite remains independent of those executables.

The caller owns destination-document insertion, selection, replacement, and
layout. Vectex stops at a normalized fragment plus geometry and edit metadata.

## 1. Repository and packaging

- Initialize an independent Git repository with `main` as the initial branch.
- Use a conventional `src/vectex` package layout and a modern PEP 517
  `pyproject.toml`.
- Declare `lxml` as the sole required runtime dependency.
- Provide `svg-py`, `drawsvg`, and `all` extras using the real distribution and
  import names (`svg.py` / `svg`, and `drawsvg` / `drawsvg`).
- Add a noarch Conda recipe whose runtime requirements match the wheel.
- Add development tasks and configuration for Ruff, mypy, pytest, wheel/sdist
  construction, and optional real-tool integration tests.
- Do not select a public license on the author's behalf; call that out as a
  release prerequisite.

## 2. Public types and error contract

- Expose `vectex.render(source, *, engine="pdflatex", converter="dvisvgm", ...)`.
- Expose an immutable `VectexFragment` with source, engine, converter, scale,
  width, height, view box, optional baseline, metadata, and stable serialization.
- Return an independently parsed lxml group from every `to_lxml()` call.
- Define exceptions for configuration/options, missing executables, compilation,
  conversion, invalid SVG, unsafe SVG, and unavailable/unsupported backends.
- Include argv, return code, stdout, stderr, and timeout context in structured
  process failures without invoking a shell.

## 3. Compiler and converter interfaces

- Define small runtime-checkable protocols for compilers and converters so
  callers can inject future implementations.
- Implement TeX drivers for pdflatex, xelatex, and lualatex. Wrap expression
  source in a minimal standalone document, allow a trusted preamble, compile in
  an isolated temporary directory, and emit PDF.
- Implement a Typst driver that writes `.typ` source and emits PDF.
- Make executable lookup explicit with `shutil.which`, while allowing exact
  executable overrides for hermetic applications and tests.
- Implement dvisvgm conversion from PDF using argument lists, captured output,
  timeouts, and path-oriented glyph output (`--no-fonts`) for portability.
- Keep compiler and converter extra arguments as sequences, never command
  strings.

## 4. SVG normalization and security

- Parse with an `lxml` XML parser configured without entity resolution, DTD
  loading, recovery, or network access.
- Require one SVG document root and a positive four-number view box (or derive
  one from numeric width/height when possible).
- Reject scripts, event-handler attributes, `foreignObject`, external hrefs,
  external `url(...)` resources, unresolved internal references, and document
  CSS `<style>` elements. Inline `style` attributes remain supported and have
  their `url(#...)` references rewritten.
- Generate a per-fragment ID namespace, prefix every existing ID, and rewrite
  `href`, `xlink:href`, and every internal `url(#...)` attribute/style reference.
- Copy required definitions and visible nodes into exactly one SVG `<g>` root.
  Preserve used namespace declarations.
- Convert source view-box offsets and requested scale into an inner group
  transform. Expose normalized width, height, and view box at the fragment
  level.
- Strip converter-only insignificant whitespace, sort attributes, and serialize
  with stable namespace prefixes and ordering so repeated serialization of one
  fragment is byte-for-byte identical.

## 5. Editable metadata

- Add a standard SVG `<metadata>` child containing namespaced Vectex elements.
- Use format version 1 with original source, engine, converter, scale, optional
  baseline, and deterministic JSON compiler/converter options.
- Store source as XML text so multiline content and XML-special characters
  round-trip without large or manually escaped `data-*` attributes.
- Keep the format version explicit and parse metadata back into public fragment
  properties to leave room for migrations.
- Also put TexText's recognized namespaced attributes on the outer `<g>`:
  encoded text, engine, preamble-file path, scale, alignment, converter marker,
  version, and transform Jacobian. Keep original unwrapped input in Vectex
  metadata; when Vectex adds a TeX math wrapper, store the compilable wrapped
  body in TexText metadata so re-editing and recompiling succeeds.
- Default to TexText-compatible output, with an opt-out for callers that want a
  metadata-minimal fragment. Test recognition against TexText's documented
  `get_all_info()` contract and current source encoding behavior.

## 6. Optional backend adapters

- `to_svg_py()` returns an `svg.Element` subclass whose `as_str()` emits the
  already-normalized group verbatim. This preserves arbitrary SVG without a
  lossy node-by-node translation.
- `to_drawsvg()` returns `drawsvg.Raw` containing the normalized group, which is
  directly appendable to a drawsvg drawing or parent group.
- Import adapters lazily and raise a focused backend exception with the correct
  extra-install hint when a dependency is absent.
- Verify each wrapper through the backend's own serialization path.

## 7. Tests and fixtures

- Check in minimal converter-output SVG fixtures for nested definitions,
  nonzero view boxes, href/xlink/url references, metadata-sensitive text, and
  unsafe/external content.
- Test exactly one group root, view-box transform/scale, nested definitions, ID
  isolation across two fragments, all reference forms, deterministic output,
  and unresolved-reference failures.
- Test metadata round trips with multiline source and `<`, `>`, `&`, quotes,
  and non-ASCII text.
- Test independent mutable lxml copies and immutable canonical output.
- Test scripts, handlers, foreign objects, stylesheets, external hrefs, and
  external CSS URLs are rejected.
- Mock executable lookup and `subprocess.run` to verify argv, working directory,
  outputs, timeouts, diagnostics, and cleanup without a TeX installation.
- Test missing programs, nonzero exits, malformed SVG, invalid dimensions,
  invalid options, and optional-backend error messages.
- Mark real pdflatex/Typst+dvisvgm tests as integration tests and skip them by
  default unless `VECTEX_RUN_INTEGRATION=1`.

## 8. Documentation and qualification

- Document purpose, non-goals, a minimal render example, adapter insertion,
  executable discovery/overrides, fragment and metadata guarantees, trust
  assumptions, integration testing, and current limitations.
- Run formatter, lint, strict type checking, all unit tests with adapters, and
  wheel/sdist builds.
- Inspect built archives to ensure fixtures/tests/private workspace data are not
  accidentally shipped.
- Run a Conda recipe render/build when a compatible builder is available;
  otherwise report that gate separately rather than implying qualification.

## Intentionally deferred after the initial slice

- Baseline extraction from compiler/converter-specific side channels. The field
  and metadata slot exist, but the default drivers return `None` until a stable
  cross-engine measurement is implemented.
- Full CSS cascading, stylesheet scoping, embedded raster-resource auditing, and
  arbitrary full-document TeX templates. Unsafe or ambiguous constructs are
  rejected instead of partially interpreted.
- Destination SVG insertion/replacement, Inkscape integration, GUI behavior,
  and converter implementations other than dvisvgm.
- Publication automation and package upload. A license choice, release CI,
  credentials, and explicit author approval are required first.
