"""Bloch sphere: a TikZ picture rendered to one editable SVG fragment.

The realistic end-to-end check for the TeX side of the pipeline. A single
picture exercises most of what a real figure needs at once: a complete
preamble with a TikZ library loaded, math labels in Dirac notation, dashed and
solid strokes, a flat fill, arrow tips, and parametric plots.

Geometry notes, since a wrong basis is visible but easy to get wrong:

  * The axes use a true orthographic projection at azimuth 60 deg and
    elevation 20 deg, so x, y, and z are the projections of an orthonormal
    frame. That is what keeps the equator inscribed exactly in the silhouette
    circle. An arbitrary-looking basis bulges the equator outside the sphere.
  * The equator is drawn with `plot`, not `arc`. Inside a 3D basis `arc`
    sweeps in the transformed frame and comes out skewed; a parametric plot of
    (cos t, sin t, 0) is exact by construction.
  * The half of the equator running behind the sphere is dashed, which is the
    only depth cue in the picture.

The sphere is filled flat rather than shaded on purpose: dvisvgm does not
translate PDF shadings in its native PDF mode, so `\\shade` and `ball color`
yield a correctly sized fragment containing nothing painted at all. See
`docs/rendering.md`.

Usage:
    python examples/bloch_sphere.py [--theta DEG] [--phi DEG] [--png]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import vectex

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

PREAMBLE = r"""\documentclass[border=2pt]{standalone}
\usepackage{tikz}
\usepackage{amsmath}
\usetikzlibrary{arrows.meta}"""

# Azimuth 60 deg, elevation 20 deg, as projections of an orthonormal frame.
_TEMPLATE = r"""
\begin{tikzpicture}[
    scale=2.4, line cap=round,
    x={(-0.8660cm,-0.1710cm)}, y={(0.5000cm,-0.2962cm)}, z={(0cm,0.9397cm)},
    axis/.style={-{Stealth[length=2mm]},thin},
    guide/.style={gray!65,thin}]
  \def\th{__THETA__} \def\ph{__PHI__}

  \fill[blue!7] (0,0) circle (1cm);
  \draw[guide]  (0,0) circle (1cm);
  \draw[guide,dashed] plot[variable=\t,domain=150:330,samples=61]
    ({cos(\t)},{sin(\t)},0);
  \draw[guide] plot[variable=\t,domain=-30:150,samples=61]
    ({cos(\t)},{sin(\t)},0);

  \draw[axis] (0,0,0) -- (0,0,1.35)  node[above]      {$\lvert 0\rangle$};
  \draw[axis] (0,0,0) -- (0,0,-1.35) node[below]      {$\lvert 1\rangle$};
  \draw[axis] (0,0,0) -- (0,1.4,0)   node[right]      {$y$};
  \draw[axis] (0,0,0) -- (1.4,0,0)   node[below left] {$x$};

  \coordinate (P)   at ({sin(\th)*cos(\ph)},{sin(\th)*sin(\ph)},{cos(\th)});
  \coordinate (Pxy) at ({sin(\th)*cos(\ph)},{sin(\th)*sin(\ph)},0);
  \draw[gray,dotted] (P) -- (Pxy) (0,0,0) -- (Pxy);
  \draw[-{Stealth[length=2.2mm]},very thick,red!80!black] (0,0,0) -- (P);
  \node[above left,inner sep=2pt] at (P) {$\lvert\psi\rangle$};

  \draw[thin] plot[variable=\s,domain=0:\th,samples=30]
    ({0.38*sin(\s)*cos(\ph)},{0.38*sin(\s)*sin(\ph)},{0.38*cos(\s)});
  \node[inner sep=1pt] at
    ({0.30*sin(\th/2)*cos(\ph)},{0.30*sin(\th/2)*sin(\ph)},{0.55*cos(\th/2)})
    {$\theta$};
  \draw[thin] plot[variable=\p,domain=0:\ph,samples=30]
    ({0.45*cos(\p)},{0.45*sin(\p)},0);
  \node[inner sep=1pt] at
    ({0.62*cos(\ph/2)},{0.62*sin(\ph/2)},0) {$\varphi$};
\end{tikzpicture}
"""


def picture(theta: float, phi: float) -> str:
    """Return the TikZ body for a state at polar *theta*, azimuth *phi*."""
    return _TEMPLATE.replace("__THETA__", f"{theta:g}").replace("__PHI__", f"{phi:g}")


def build(theta: float = 50.0, phi: float = 40.0) -> vectex.VectexFragment:
    """Render the sphere and return the fragment."""
    return vectex.render(picture(theta, phi), preamble=PREAMBLE)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a Bloch sphere to SVG.")
    ap.add_argument("--theta", type=float, default=50.0, help="polar angle, degrees")
    ap.add_argument("--phi", type=float, default=40.0, help="azimuth, degrees")
    ap.add_argument("--output-dir", type=Path, default=OUT, help="where to write")
    ap.add_argument("--png", action="store_true", help="also rasterize, needs cairosvg")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    fragment = build(args.theta, args.phi)
    target = args.output_dir / "bloch_sphere.svg"
    fragment.write_svg_document(target)
    if args.png:
        # Rasterizing is deliberately not vectex's job; cairosvg is example-only.
        import cairosvg

        cairosvg.svg2png(url=str(target), write_to=str(target.with_suffix(".png")))
    print(
        f"bloch_sphere  {fragment.width:6.1f}x{fragment.height:<6.1f}"
        f"  theta={args.theta:g} phi={args.phi:g}  -> {target.name}"
    )


if __name__ == "__main__":
    main()
