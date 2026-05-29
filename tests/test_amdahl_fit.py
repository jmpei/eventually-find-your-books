import math
from analysis.amdahl.fit import amdahl_speedup, fit_serial_fraction


def test_amdahl_speedup_formula():
    # f=0 -> linear speedup; f=1 -> no speedup
    assert math.isclose(amdahl_speedup(8, 0.0), 8.0)
    assert math.isclose(amdahl_speedup(8, 1.0), 1.0)


def test_fit_recovers_known_f():
    true_f = 0.2
    ns = [1, 2, 4, 8, 16, 26]
    points = [(n, amdahl_speedup(n, true_f)) for n in ns]
    est_f = fit_serial_fraction(points)
    assert abs(est_f - true_f) < 0.01


def test_fit_handles_noise():
    true_f = 0.35
    ns = [1, 2, 4, 8, 16, 26]
    # deterministic small perturbation (no RNG)
    points = [(n, amdahl_speedup(n, true_f) * (1 + 0.01 * ((i % 3) - 1)))
              for i, n in enumerate(ns)]
    est_f = fit_serial_fraction(points)
    assert abs(est_f - true_f) < 0.05
