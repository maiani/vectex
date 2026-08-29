"""Render LaTeX or Typst into portable SVG group fragments."""

from importlib.metadata import PackageNotFoundError, version

from .api import RenderItem, clear_cache, render, render_many
from .compiler import (
    CompilationResult,
    Compiler,
    CompileRequest,
    TeXCompiler,
    TypstCompiler,
)
from .converter import (
    ConversionResult,
    Converter,
    ConvertRequest,
    DvisvgmConverter,
)
from .exceptions import (
    CompilationError,
    ConfigurationError,
    ConversionError,
    InvalidSVGError,
    MissingExecutableError,
    UnsafeSVGError,
    UnsupportedBackendError,
    VectexError,
)
from .fragment import VectexFragment
from .normalizer import METADATA_VERSION, TEXTEXT_NS, VECTEX_NS, Normalizer

__all__ = [
    "METADATA_VERSION",
    "TEXTEXT_NS",
    "VECTEX_NS",
    "CompilationError",
    "CompilationResult",
    "CompileRequest",
    "Compiler",
    "ConfigurationError",
    "ConversionError",
    "ConversionResult",
    "ConvertRequest",
    "Converter",
    "DvisvgmConverter",
    "InvalidSVGError",
    "MissingExecutableError",
    "Normalizer",
    "RenderItem",
    "TeXCompiler",
    "TypstCompiler",
    "UnsafeSVGError",
    "UnsupportedBackendError",
    "VectexError",
    "VectexFragment",
    "__version__",
    "clear_cache",
    "render",
    "render_many",
]

try:
    __version__ = version("vectex")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0+unknown"
