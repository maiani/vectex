"""Render LaTeX or Typst into portable SVG group fragments."""

from .api import render
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
    "TeXCompiler",
    "TypstCompiler",
    "UnsafeSVGError",
    "UnsupportedBackendError",
    "VectexError",
    "VectexFragment",
    "render",
]

__version__ = "0.1.0"
