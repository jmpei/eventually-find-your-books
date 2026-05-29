"""
Estimate the serial fraction f of the A-Z scatter-gather search via Amdahl's Law.

Two independent estimates, cross-validated:
  (1) Least-squares fit of measured speedup S(N) to Amdahl's model.
  (2) Phase-profiling: serial fraction approximated from the aggregate phase share.

Amdahl's Law:   S(N) = 1 / ( f + (1 - f) / N )

Linearize for a closed-form least-squares fit (no scipy needed):
    1/S = f + (1-f)/N  =>  (1/S - 1/N) = f * (1 - 1/N)
    => y = f * x   with   y = 1/S - 1/N,  x = 1 - 1/N
    => f_hat = sum(x*y) / sum(x*x)
"""
import csv
from pathlib import Path
from typing import List, Tuple

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def amdahl_speedup(n: int, f: float) -> float:
    """Ideal speedup at N workers given serial fraction f."""
    return 1.0 / (f + (1.0 - f) / n)


def fit_serial_fraction(points: List[Tuple[float, float]]) -> float:
    """
    Least-squares estimate of f from (n_workers, speedup) points.
    Points at n=1 contribute x=0 and are naturally ignored by the fit.
    """
    num = 0.0
    den = 0.0
    for n, s in points:
        if n <= 1 or s <= 0:
            continue
        x = 1.0 - 1.0 / n
        y = 1.0 / s - 1.0 / n
        num += x * y
        den += x * x
    if den == 0:
        raise ValueError("Need at least one point with n > 1 to fit f")
    f = num / den
    return max(0.0, min(1.0, f))  # clamp to [0,1]


def serial_fraction_from_phases(aggregate_s: float, total_s: float) -> float:
    """Phase-profiling estimate: serial share = aggregate / total (the part that
    does not shrink as workers are added)."""
    if total_s <= 0:
        return 0.0
    return max(0.0, min(1.0, aggregate_s / total_s))


def load_speedup_csv(path: Path) -> List[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def analyze(csv_path: Path = RESULTS_DIR / "speedup.csv") -> dict:
    rows = load_speedup_csv(csv_path)
    points = [(float(r["n_workers"]), float(r["speedup"])) for r in rows]
    f_lsq = fit_serial_fraction(points)

    base = next(r for r in rows if int(r["n_workers"]) == 1)
    f_phase = serial_fraction_from_phases(
        float(base["aggregate_s"]), float(base["total_s"])
    )
    return {"f_least_squares": f_lsq, "f_phase_profiling": f_phase, "rows": rows}


def plot(csv_path: Path = RESULTS_DIR / "speedup.csv") -> Path:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = analyze(csv_path)
    rows = res["rows"]
    ns = [float(r["n_workers"]) for r in rows]
    sp = [float(r["speedup"]) for r in rows]
    f = res["f_least_squares"]

    grid = np.linspace(min(ns), max(ns), 100)
    model = [amdahl_speedup(n, f) for n in grid]

    plt.figure(figsize=(7, 5))
    plt.plot(ns, sp, "o", label="measured")
    plt.plot(grid, model, "-", label=f"Amdahl fit (f={f:.3f})")
    plt.xlabel("workers (N)")
    plt.ylabel("speedup  S(N)=T(1)/T(N)")
    plt.title("A-Z scatter-gather speedup vs Amdahl model")
    plt.legend()
    out = RESULTS_DIR / "speedup.png"
    plt.savefig(out, dpi=120, bbox_inches="tight")
    return out


def main():
    res = analyze()
    print(f"Serial fraction f (least-squares fit):  {res['f_least_squares']:.4f}")
    print(f"Serial fraction f (phase profiling):    {res['f_phase_profiling']:.4f}")
    diff = abs(res["f_least_squares"] - res["f_phase_profiling"])
    print(f"Cross-validation gap:                   {diff:.4f}")
    out = plot()
    print(f"Plot written to: {out}")


if __name__ == "__main__":
    main()
