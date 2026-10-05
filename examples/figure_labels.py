"""Figure labels: a batch of maths labels rendered in one TeX run.

The complement to `bloch_sphere.py`. That example puts one elaborate picture
through the pipeline; this one puts many small fragments through it, which is
what labelling a figure actually looks like and what exercises the parts a
single render never touches:

  * `render_many` groups items that share a compilation, so these labels cost
    one TeX invocation rather than one each. Items only differ in size here,
    which is exactly the case that stays grouped.
  * `size_pt` asks for a font size semantically, instead of the geometric
    `scale`.
  * `baseline` is what a caller aligns a label against when placing it next to
    an axis; a picture has none, an inline formula does.
  * The persistent cache is keyed on the installed TeX and dvisvgm, so a
    second run with the same cache directory returns without compiling.

Usage:
    python examples/figure_labels.py [--size-pt PT] [--cache-dir DIR]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import vectex

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

LABELS = {
    "energy": r"$E = \hbar\omega$",
    "gap": r"$\Delta(T)/\Delta_0$",
    "operator": r"$\hat{H} = \sum_i \epsilon_i c_i^{\dagger} c_i$",
    "axis": r"temperature $T$ (K)",
    "matrix": r"$\begin{pmatrix} 0 & \Delta \\ \Delta^{*} & 0\end{pmatrix}$",
}


def build(
    size_pt: float = 9.0,
    cache_dir: str | Path | None = None,
    refresh: bool = False,
) -> tuple[vectex.VectexFragment, ...]:
    """Render every label in one batch and return the fragments in order."""
    return vectex.render_many(
        list(LABELS.values()),
        size_pt=size_pt,
        cache_dir=cache_dir,
        refresh=refresh,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a batch of figure labels.")
    ap.add_argument("--size-pt", type=float, default=9.0, help="font size in points")
    ap.add_argument("--output-dir", type=Path, default=OUT, help="where to write")
    ap.add_argument("--cache-dir", type=Path, default=None, help="persistent cache")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    fragments = build(args.size_pt, args.cache_dir, refresh=True)
    elapsed = time.perf_counter() - started

    for name, fragment in zip(LABELS, fragments, strict=True):
        target = args.output_dir / f"label_{name}.svg"
        fragment.write_svg_document(target)
        baseline = "none" if fragment.baseline is None else f"{fragment.baseline:.2f}"
        print(
            f"{name:>9}  {fragment.width:6.1f}x{fragment.height:<5.1f}"
            f"  baseline {baseline:>6}  -> {target.name}"
        )
    print(f"{len(fragments)} labels in one compilation, {elapsed:.2f}s")

    if args.cache_dir is not None:
        started = time.perf_counter()
        build(args.size_pt, args.cache_dir)
        print(f"second run from cache: {time.perf_counter() - started:.2f}s")


if __name__ == "__main__":
    main()
