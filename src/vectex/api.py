"""High-level rendering API."""

from __future__ import annotations

import math
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from .compiler import (
    Compiler,
    CompileRequest,
    compiler_from_name,
    normalize_args,
    tex_body,
)
from .converter import Converter, ConvertRequest, converter_from_name
from .exceptions import ConfigurationError
from .fragment import VectexFragment
from .normalizer import Normalizer

_TEXTEXT_ENGINES = frozenset({"pdflatex", "xelatex", "lualatex", "typst"})


def render(
    source: str,
    *,
    engine: str | Compiler = "pdflatex",
    converter: str | Converter = "dvisvgm",
    scale: float = 1.0,
    timeout: float = 30.0,
    preamble: str = "",
    math_mode: bool = True,
    compiler_args: Sequence[str] = (),
    converter_args: Sequence[str] = (),
    executable_overrides: Mapping[str, str] | None = None,
    id_prefix: str | None = None,
    baseline: float | None = None,
    textext_compatible: bool = True,
    textext_preamble_file: str = "",
    textext_alignment: str = "middle center",
) -> VectexFragment:
    """Compile *source* and return one portable SVG group fragment.

    ``engine`` and ``converter`` may be built-in names or objects implementing
    the public protocols. External commands execute once per stage in a fresh
    temporary directory without a shell.
    """
    if not isinstance(source, str) or not source.strip():
        raise ConfigurationError("source must be a non-empty string")
    if not isinstance(preamble, str):
        raise ConfigurationError("preamble must be a string")
    if not isinstance(math_mode, bool):
        raise ConfigurationError("math_mode must be a boolean")
    if not isinstance(textext_compatible, bool):
        raise ConfigurationError("textext_compatible must be a boolean")
    if not isinstance(textext_preamble_file, str):
        raise ConfigurationError("textext_preamble_file must be a string")
    if not isinstance(textext_alignment, str) or not textext_alignment.strip():
        raise ConfigurationError("textext_alignment must be a non-empty string")
    timeout_value = _positive_timeout(timeout)
    compiler_extra = normalize_args(compiler_args, option="compiler_args")
    converter_extra = normalize_args(converter_args, option="converter_args")
    overrides = _executable_overrides(executable_overrides)

    compiler_impl = compiler_from_name(engine) if isinstance(engine, str) else engine
    converter_impl = (
        converter_from_name(converter) if isinstance(converter, str) else converter
    )
    _component(compiler_impl, "compiler")
    _component(converter_impl, "converter")
    engine_name = compiler_impl.name
    converter_name = converter_impl.name
    if textext_compatible and engine_name not in _TEXTEXT_ENGINES:
        raise ConfigurationError(
            f"TexText does not support compiler {engine_name!r}; "
            "pass textext_compatible=False for custom engines"
        )

    with tempfile.TemporaryDirectory(prefix="vectex-") as temporary:
        workdir = Path(temporary)
        compiled = compiler_impl.compile(
            CompileRequest(
                source=source,
                workdir=workdir,
                timeout=timeout_value,
                preamble=preamble,
                math_mode=math_mode,
                extra_args=compiler_extra,
                executable=overrides.get(engine_name),
            )
        )
        converted = converter_impl.convert(
            ConvertRequest(
                compiled=compiled,
                workdir=workdir,
                timeout=timeout_value,
                extra_args=converter_extra,
                executable=overrides.get(converter_name),
            )
        )
        try:
            svg = converted.path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(
                f"converter result cannot be read: {converted.path}"
            ) from exc
        textext_source = (
            tex_body(source, math_mode) if engine_name != "typst" else source
        )
        return Normalizer().normalize(
            svg,
            source=source,
            engine=engine_name,
            converter=converter_name,
            scale=scale,
            baseline=baseline,
            compiler_options={
                "args": list(compiler_extra),
                "math_mode": math_mode,
                "preamble": preamble,
            },
            converter_options={"args": list(converter_extra)},
            id_prefix=id_prefix,
            textext_compatible=textext_compatible,
            textext_source=textext_source,
            textext_preamble_file=textext_preamble_file,
            textext_alignment=textext_alignment,
        )


def _positive_timeout(value: float) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("timeout must be a positive finite number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigurationError("timeout must be a positive finite number")
    return timeout


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
