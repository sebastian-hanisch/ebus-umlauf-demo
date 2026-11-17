"""Gemeinsame Fixtures: die Mini-Instanz, an der jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b), und kurze Zeitlimits für die App-Tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ebu_constants as C  # noqa: E402
import ebu_scenario as S  # noqa: E402


@pytest.fixture
def mini():
    """4 Fahrten à 10 km (13 kWh), Wendezeit 3 min, Leerfahrt 24 min. Handrechnung der Anschlüsse:
    t0 360–400 A→B, t1 370–410 B→A, t2 420–460 A→B, t3 430–470 B→A.
    (0,3): endet in B, t3 startet in B, Wartezeit 30 min, Spielraum 27; (1,2): endet in A, t2 startet in A, Wartezeit 10 min, Spielraum 7.
    (0,2) und (1,3) brauchen eine Leerfahrt (27 min) bei 20 min Wartezeit: kein Anschluss. Maximales Matching 2, Dieselumlauf 4 − 2 = 2 Busse."""
    return S.make_instance([(360, 400, 0), (370, 410, 1), (420, 460, 0), (430, 470, 1)], 10.0)


@pytest.fixture(autouse=True)
def kurze_zeitlimits(monkeypatch):
    """Die App rechnet exakt mit Zeitlimit: in den Tests kurz halten (geprüft wird, dass nichts abstürzt, nicht die Beweise)."""
    monkeypatch.setattr(C, "EXACT_TIME_LIMIT_S", 3.0)
    monkeypatch.setattr(C, "RAMP_TIME_LIMIT_S", 1.0)
