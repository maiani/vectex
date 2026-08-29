"""High-level rendering API."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, cast

from . import cache
from .compiler import (
    Compiler,
    CompileRequest,
    compiler_from_name,
    normalize_args,
    tex_base_size,
)
from .converter import Converter, ConvertRequest, converter_from_name
from .exceptions import ConfigurationError
from .fragment import VectexFragment
from .normalizer import Normalizer
from .process import tool_identity

_TEXTEXT_ENGINES = frozenset({"pdflatex", "xelatex", "lualatex", "typst"})


@dataclass(frozen=True)
class RenderItem:
    """One source together with the options that shape its fragment.

    Every option that determines what is produced can be set here. Options left
    as ``None`` take the value passed to :func:`render` or :func:`render_many`.
    ``cache_dir``, ``refresh`` and ``unique_ids`` describe how a call is
    executed rather than what it produces, and stay on the call itself.

    :func:`render_many` groups items that share a compilation -- the same
    engine, converter, preamble, timeout, process arguments and executable
    overrides -- and runs one compiler and converter invocation per group.
    """

    source: str
    engine: str | Compiler | None = None
    converter: str | Converter | None = None
    scale: float | None = None
    size_pt: float | None = None
    timeout: float | None = None
    preamble: str | None = None
    compiler_args: Sequence[str] | None = None
    converter_args: Sequence[str] | None = None
    executable_overrides: Mapping[str, str] | None = None
    id_prefix: str | None = None
    baseline: float | None = None
    textext_compatible: bool | None = None
    textext_preamble_file: str | None = None
    textext_alignment: str | None = None


@dataclass(frozen=True)
class _Resolved:
    """One item with every option resolved to a concrete value."""

    source: str
    compiler: Compiler
    converter: Converter
    timeout: float
    preamble: str
    scale: float
    size_pt: float | None
    baseline: float | None
    id_prefix: str | None
    compiler_args: tuple[str, ...]
    converter_args: tuple[str, ...]
    overrides: Mapping[str, str]
    textext_compatible: bool
    textext_preamble_file: str
    textext_alignment: str
    compilation: tuple[Any, ...]
    cacheable: bool


def render(
    source: str | RenderItem,
    *,
    engine: str | Compiler = "pdflatex",
    converter: str | Converter = "dvisvgm",
    scale: float | None = None,
    size_pt: float | None = None,
    timeout: float = 30.0,
    preamble: str = "",
    compiler_args: Sequence[str] = (),
    converter_args: Sequence[str] = (),
    executable_overrides: Mapping[str, str] | None = None,
    id_prefix: str | None = None,
    unique_ids: bool = False,
    baseline: float | None = None,
    cache_dir: str | PathLike[str] | None = None,
    refresh: bool = False,
    textext_compatible: bool = True,
    textext_preamble_file: str = "",
    textext_alignment: str = "middle center",
) -> VectexFragment:
    """Compile *source* as a literal TeX document body and return one SVG fragment.

    Use normal TeX delimiters such as ``$...$`` or ``\\[...\\]`` for mathematics.
    *source* may also be a :class:`RenderItem`, whose options override the
    keywords here.
    """
    return render_many(
        (source,),
        engine=engine,
        converter=converter,
        scale=scale,
        size_pt=size_pt,
        timeout=timeout,
        preamble=preamble,
        compiler_args=compiler_args,
        converter_args=converter_args,
        executable_overrides=executable_overrides,
        id_prefix=id_prefix,
        unique_ids=unique_ids,
        baseline=baseline,
        cache_dir=cache_dir,
        refresh=refresh,
        textext_compatible=textext_compatible,
        textext_preamble_file=textext_preamble_file,
        textext_alignment=textext_alignment,
    )[0]


def render_many(
    sources: Sequence[str | RenderItem],
    *,
    engine: str | Compiler = "pdflatex",
    converter: str | Converter = "dvisvgm",
    scale: float | None = None,
    size_pt: float | None = None,
    timeout: float = 30.0,
    preamble: str = "",
    compiler_args: Sequence[str] = (),
    converter_args: Sequence[str] = (),
    executable_overrides: Mapping[str, str] | None = None,
    id_prefix: str | None = None,
    unique_ids: bool = False,
    baseline: float | None = None,
    cache_dir: str | PathLike[str] | None = None,
    refresh: bool = False,
    textext_compatible: bool = True,
    textext_preamble_file: str = "",
    textext_alignment: str = "middle center",
) -> tuple[VectexFragment, ...]:
    """Render several sources, sharing invocations wherever the options allow.

    A source may be a string or a :class:`RenderItem` carrying its own options.
    Items that share a compilation are compiled together, so a batch of labels
    differing only in size still costs one compiler and one converter run,
    while an item with its own preamble simply forms its own group. Fragments
    are returned in input order.
    """
    if not isinstance(unique_ids, bool):
        raise ConfigurationError("unique_ids must be a boolean")
    if not isinstance(refresh, bool):
        raise ConfigurationError("refresh must be a boolean")
    defaults = RenderItem(
        source="",
        engine=engine,
        converter=converter,
        scale=scale,
        size_pt=size_pt,
        timeout=timeout,
        preamble=preamble,
        compiler_args=compiler_args,
        converter_args=converter_args,
        executable_overrides=executable_overrides,
        id_prefix=id_prefix,
        baseline=baseline,
        textext_compatible=textext_compatible,
        textext_preamble_file=textext_preamble_file,
        textext_alignment=textext_alignment,
    )
    entries = _entries(sources)
    components: dict[Any, Compiler | Converter] = {}
    items = tuple(
        _resolve(entry, defaults, index, len(entries), components)
        for index, entry in enumerate(entries)
    )
    if unique_ids and any(item.id_prefix is not None for item in items):
        raise ConfigurationError("id_prefix and unique_ids are alternatives")

    root = cache.cache_root(cache_dir)
    if root is not None:
        if any(not item.cacheable for item in items):
            raise ConfigurationError("disk caching requires named built-in components")
        if unique_ids:
            raise ConfigurationError("unique_ids cannot be combined with disk caching")
    keys = tuple(_cache_key(item, cached=root is not None) for item in items)

    results: list[VectexFragment | None] = [None] * len(items)
    misses: list[int] = []
    for index, key in enumerate(keys):
        cached = cache.load(root, key) if root is not None and not refresh else None
        if cached is None:
            misses.append(index)
        else:
            results[index] = cached

    for indices in _compilation_groups(items, misses):
        rendered = _render_uncached(
            tuple(items[index] for index in indices),
            tuple(
                _prefix(items[index].id_prefix, unique_ids, keys[index])
                for index in indices
            ),
        )
        for index, fragment in zip(indices, rendered, strict=True):
            results[index] = fragment
            if root is not None:
                cache.store(root, keys[index], fragment)
    if any(fragment is None for fragment in results):  # pragma: no cover
        raise AssertionError("internal render result was not populated")
    return cast(tuple[VectexFragment, ...], tuple(results))


def clear_cache(cache_dir: str | PathLike[str] | None = None) -> int:
    """Clear Vectex entries from the configured cache and return their count."""
    return cache.clear(cache_dir)


def _render_uncached(
    items: tuple[_Resolved, ...], prefixes: tuple[str, ...]
) -> tuple[VectexFragment, ...]:
    """Compile and normalize one group of items sharing a compilation."""
    shared = items[0]
    compiler_impl = shared.compiler
    converter_impl = shared.converter
    with tempfile.TemporaryDirectory(prefix="vectex-") as temporary:
        workdir = Path(temporary)
        requests = tuple(
            CompileRequest(
                source=item.source,
                workdir=workdir,
                timeout=shared.timeout,
                preamble=shared.preamble,
                extra_args=shared.compiler_args,
                executable=shared.overrides.get(compiler_impl.name),
            )
            for item in items
        )
        if len(requests) == 1:
            compiled = compiler_impl.compile(requests[0])
        else:
            compile_many = getattr(compiler_impl, "compile_many", None)
            if not callable(compile_many):
                raise ConfigurationError("compiler does not support render_many")
            compiled = compile_many(requests)
        convert_request = ConvertRequest(
            compiled=compiled,
            workdir=workdir,
            timeout=shared.timeout,
            extra_args=shared.converter_args,
            executable=shared.overrides.get(converter_impl.name),
        )
        if len(requests) == 1:
            converted = (converter_impl.convert(convert_request),)
        else:
            convert_many = getattr(converter_impl, "convert_many", None)
            if not callable(convert_many):
                raise ConfigurationError("converter does not support render_many")
            converted = tuple(convert_many(convert_request))
        if len(converted) != len(items):
            raise ConfigurationError("converter returned the wrong number of pages")
        ratios = compiled.baseline_ratios or (None,) * len(items)
        fragments = []
        for item, prefix, page, ratio in zip(
            items, prefixes, converted, ratios, strict=True
        ):
            try:
                svg = page.path.read_bytes()
            except OSError as exc:
                raise ConfigurationError(
                    f"converter result cannot be read: {page.path}"
                ) from exc
            fragments.append(
                Normalizer().normalize(
                    svg,
                    source=item.source,
                    engine=compiler_impl.name,
                    converter=converter_impl.name,
                    scale=item.scale,
                    baseline=item.baseline,
                    baseline_ratio=ratio,
                    compiler_options={
                        "args": list(shared.compiler_args),
                        "preamble": shared.preamble,
                        "size_pt": item.size_pt,
                    },
                    converter_options={"args": list(shared.converter_args)},
                    id_prefix=prefix,
                    textext_compatible=item.textext_compatible,
                    textext_source=item.source,
                    textext_preamble_file=item.textext_preamble_file,
                    textext_alignment=item.textext_alignment,
                )
            )
        return tuple(fragments)


def _entries(value: Sequence[str | RenderItem]) -> tuple[RenderItem, ...]:
    """Normalize a batch of plain sources or per-item records."""
    if isinstance(value, (str, bytes, RenderItem)):
        raise ConfigurationError("sources must be a non-empty sequence of strings")
    entries = tuple(
        entry if isinstance(entry, RenderItem) else RenderItem(entry) for entry in value
    )
    if not entries or not all(
        isinstance(entry.source, str) and entry.source.strip() for entry in entries
    ):
        raise ConfigurationError("sources must be a non-empty sequence of strings")
    return entries


def _resolve(
    entry: RenderItem,
    defaults: RenderItem,
    index: int,
    count: int,
    components: dict[Any, Compiler | Converter],
) -> _Resolved:
    """Merge one entry with the batch defaults and validate the result."""

    def chosen(name: str) -> Any:
        value = getattr(entry, name)
        return getattr(defaults, name) if value is None else value

    preamble = chosen("preamble")
    if not isinstance(preamble, str):
        raise ConfigurationError("preamble must be a string")
    textext_compatible = chosen("textext_compatible")
    if not isinstance(textext_compatible, bool):
        raise ConfigurationError("textext_compatible must be a boolean")
    textext_preamble_file = chosen("textext_preamble_file")
    if not isinstance(textext_preamble_file, str):
        raise ConfigurationError("textext_preamble_file must be a string")
    textext_alignment = chosen("textext_alignment")
    if not isinstance(textext_alignment, str) or not textext_alignment.strip():
        raise ConfigurationError("textext_alignment must be a non-empty string")

    engine_spec = chosen("engine")
    converter_spec = chosen("converter")
    compiler_impl = cast(
        Compiler, _component_for(engine_spec, compiler_from_name, components)
    )
    converter_impl = cast(
        Converter, _component_for(converter_spec, converter_from_name, components)
    )
    _component(compiler_impl, "compiler")
    _component(converter_impl, "converter")
    if textext_compatible and compiler_impl.name not in _TEXTEXT_ENGINES:
        raise ConfigurationError(
            f"TexText does not support compiler {compiler_impl.name!r}; "
            "pass textext_compatible=False for custom engines"
        )

    # An item that sets either sizing option replaces the pair, so a batch
    # size_pt does not collide with a per-item scale.
    if entry.scale is None and entry.size_pt is None:
        scale_input, size_pt = defaults.scale, defaults.size_pt
    else:
        scale_input, size_pt = entry.scale, entry.size_pt
    overrides = _executable_overrides(chosen("executable_overrides"))
    compiler_args = normalize_args(chosen("compiler_args"), option="compiler_args")
    converter_args = normalize_args(chosen("converter_args"), option="converter_args")
    timeout = _positive_timeout(chosen("timeout"))
    id_prefix = (
        entry.id_prefix
        if entry.id_prefix is not None
        else _batch_prefix(defaults.id_prefix, index, count)
    )
    return _Resolved(
        source=entry.source,
        compiler=compiler_impl,
        converter=converter_impl,
        timeout=timeout,
        preamble=preamble,
        scale=_effective_scale(scale_input, size_pt, preamble, engine_spec),
        size_pt=size_pt,
        baseline=chosen("baseline"),
        id_prefix=id_prefix,
        compiler_args=compiler_args,
        converter_args=converter_args,
        overrides=overrides,
        textext_compatible=textext_compatible,
        textext_preamble_file=textext_preamble_file,
        textext_alignment=textext_alignment,
        compilation=(
            _spec_key(engine_spec),
            _spec_key(converter_spec),
            timeout,
            preamble,
            compiler_args,
            converter_args,
            tuple(sorted(overrides.items())),
        ),
        cacheable=isinstance(engine_spec, str) and isinstance(converter_spec, str),
    )


def _component_for(
    spec: Any,
    factory: Any,
    components: dict[Any, Compiler | Converter],
) -> Compiler | Converter:
    """Reuse one component instance per distinct engine or converter spec."""
    key = _spec_key(spec)
    if key not in components:
        components[key] = factory(spec) if isinstance(spec, str) else spec
    return components[key]


def _spec_key(spec: Any) -> Any:
    return spec if isinstance(spec, str) else id(spec)


def _compilation_groups(
    items: tuple[_Resolved, ...], indices: Sequence[int]
) -> tuple[tuple[int, ...], ...]:
    """Group item positions that can share one compiler and converter run."""
    groups: dict[tuple[Any, ...], list[int]] = {}
    for index in indices:
        groups.setdefault(items[index].compilation, []).append(index)
    return tuple(tuple(group) for group in groups.values())


def _cache_key(item: _Resolved, *, cached: bool) -> str:
    """Fingerprint every input that determines the fragment."""
    fields: dict[str, Any] = {
        "baseline": item.baseline,
        "compiler_args": list(item.compiler_args),
        "converter": item.converter.name,
        "converter_args": list(item.converter_args),
        "engine": item.compiler.name,
        "executable_overrides": dict(item.overrides),
        "id_prefix": item.id_prefix,
        "preamble": item.preamble,
        "scale": item.scale,
        "size_pt": item.size_pt,
        "source": item.source,
        "textext_alignment": item.textext_alignment,
        "textext_compatible": item.textext_compatible,
        "textext_preamble_file": item.textext_preamble_file,
    }
    if cached:
        # A record compiled by one installation must not be served after that
        # installation changes, so the tools identify themselves in the key.
        fields["toolchain"] = [
            _component_identity(component, item.overrides)
            for component in (item.compiler, item.converter)
        ]
    return _fingerprint(fields)


def _component_identity(
    component: Compiler | Converter, overrides: Mapping[str, str]
) -> str:
    """Identify the installed tool behind a component for cache keys.

    A component may report its own identity; built-in components fall back to
    probing the executable, which is why a compiled record is not reused after
    the TeX or converter installation changes.
    """
    declared = getattr(component, "identity", None)
    if callable(declared):
        return str(declared())
    name = component.name
    return tool_identity(overrides.get(name, name))


def _batch_prefix(id_prefix: str | None, index: int, count: int) -> str | None:
    """Spread one batch prefix over several fragments without collisions."""
    if id_prefix is None or count == 1:
        return id_prefix
    return f"{id_prefix}-{index}"


def _effective_scale(
    scale: float | None, size_pt: float | None, preamble: str, engine: str | Compiler
) -> float:
    if scale is not None and size_pt is not None:
        raise ConfigurationError("scale and size_pt are alternatives")
    if size_pt is None:
        return _positive_number(1.0 if scale is None else scale, "scale")
    size = _positive_number(size_pt, "size_pt")
    engine_name = engine if isinstance(engine, str) else engine.name
    base = 11.0 if engine_name == "typst" else tex_base_size(preamble)
    return size / base


def _prefix(explicit: str | None, unique: bool, key: str) -> str:
    if unique:
        return f"vx-{uuid.uuid4().hex[:12]}"
    if explicit is None:
        return f"vx{key[:12]}"
    return explicit


def _fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.blake2s(encoded.encode("utf-8")).hexdigest()


def _positive_number(value: float, option: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{option} must be a positive finite number") from exc
    if not math.isfinite(number) or number <= 0:
        raise ConfigurationError(f"{option} must be a positive finite number")
    return number


def _positive_timeout(value: float) -> float:
    return _positive_number(value, "timeout")


def _executable_overrides(value: Mapping[str, str] | None) -> dict[str, str]:
    if value is None:
        return {}
    try:
        overrides = dict(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            "executable_overrides must map component names to executable strings"
        ) from exc
    if not all(
        isinstance(key, str)
        and isinstance(executable, str)
        and executable
        and "\x00" not in executable
        for key, executable in overrides.items()
    ):
        raise ConfigurationError(
            "executable_overrides must map names to non-empty NUL-free strings"
        )
    return overrides


def _component(value: object, kind: str) -> None:
    if not isinstance(getattr(value, "name", None), str) or not callable(
        getattr(value, "compile" if kind == "compiler" else "convert", None)
    ):
        raise ConfigurationError(f"{kind} does not implement the vectex protocol")
