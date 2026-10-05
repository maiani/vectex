"""Build the picture at the top of the README.

A display equation typeset by real TeX and returned as an SVG fragment, set on
a white rectangle with a margin so it reads on a dark page too.  Needs a TeX
installation with ``pdflatex`` and ``dvisvgm``.

Usage:
    python docs/readme_figure.py
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

import vectex

OUT = Path(__file__).resolve().parent / "images" / "readme.svg"
SVG = "http://www.w3.org/2000/svg"

EQUATION = r"""\[
  i\hbar\,\frac{\partial}{\partial t}\,\Psi(\mathbf{r}, t)
  = \Bigl[-\frac{\hbar^{2}}{2m}\,\nabla^{2} + V(\mathbf{r}, t)\Bigr]
    \,\Psi(\mathbf{r}, t)
\]"""


def on_white(document: str, margin: float) -> str:
    """The document grown by ``margin`` all round, on an opaque white rectangle."""
    root = etree.fromstring(document.encode("utf-8"))
    x, y, w, h = (float(v) for v in root.get("viewBox", "").replace(",", " ").split())
    x, y, w2, h2 = x - margin, y - margin, w + 2 * margin, h + 2 * margin
    root.set("viewBox", f"{x:g} {y:g} {w2:g} {h2:g}")
    for attr, old, new in (("width", w, w2), ("height", h, h2)):
        value = root.get(attr)
        if value:
            number = float("".join(c for c in value if c in "0123456789.-"))
            unit = value.lstrip("0123456789.-")
            root.set(attr, f"{number * new / old:g}{unit}")
    rect = etree.Element(
        f"{{{SVG}}}rect",
        x=f"{x:g}",
        y=f"{y:g}",
        width=f"{w2:g}",
        height=f"{h2:g}",
        fill="#ffffff",
    )
    rect.set("id", "background")
    root.insert(0, rect)
    return etree.tostring(root, encoding="unicode") + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fragment = vectex.render(EQUATION, size_pt=14, id_prefix="schrodinger")
    OUT.write_text(on_white(fragment.to_svg_document(), margin=6.0), encoding="utf-8")
    print(f"wrote {OUT}")
