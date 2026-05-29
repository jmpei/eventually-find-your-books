import math
import pytest
from analysis.amdahl.fit import amdahl_speedup, fit_serial_fraction, serial_fraction_from_phases


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


def test_serial_fraction_from_phases():
    assert serial_fraction_from_phases(0.3, 1.0) == pytest.approx(0.3)
    assert serial_fraction_from_phases(1.5, 1.0) == 1.0   # clamped
    assert serial_fraction_from_phases(0.3, 0.0) == 0.0   # guard


def test_fit_raises_on_empty_or_only_n1():
    with pytest.raises(ValueError):
        fit_serial_fraction([])
    with pytest.raises(ValueError):
        fit_serial_fraction([(1, 1.0)])
