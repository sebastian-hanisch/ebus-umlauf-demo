"""Die Messreihen (tools/messreihe.py) sind vollständig und in sich stimmig: Raster, Prüfer, Schranken, Zweige (keine Nullspalten), Monotonie, Ladeplatz-Kreuzprobe.

Die Rohdaten liegen unter tools/messdaten/; die App liest nur data/messreihe.json (von tools/messreihe_auswertung.py erzeugt). Diese Tests binden beide aneinander."""

import itertools
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import messreihe as M  # noqa: E402
import messreihe_auswertung as A  # noqa: E402

import ebu_constants as C  # noqa: E402
import ebu_energy as E  # noqa: E402
import ebu_exact as X  # noqa: E402
import ebu_scenario as S  # noqa: E402

RULES5 = ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen")


@pytest.fixture(scope="module")
def data():
    return json.loads((ROOT / "data" / "messreihe.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    return {part: A.load(part) for part in ("rampe", "plaetze", "gemischt", "takt", "tag", "tag2", "regeln")}


def _key(r):
    return json.dumps({k: r.get(k) for k in ("part", "timetable", "seed", "season", "c", "p", "chargers", "slots", "reserve_buses")}, sort_keys=True)


@pytest.mark.parametrize("part,rows", [("rampe", 640), ("plaetze", 360), ("gemischt", 240), ("takt", 180), ("tag", 60), ("tag2", 20), ("regeln", 12800)])
def test_every_part_covers_its_whole_grid_exactly_once(raw, part, rows):
    cells = [_key(c) for c in M.grid(part)]
    assert len(cells) == rows
    assert sorted(_key(r) for r in raw[part]) == sorted(cells)


def test_the_independent_checker_rejected_nothing(raw):
    for part in ("rampe", "plaetze", "takt", "tag", "tag2"):
        for r in raw[part]:
            assert r["rules_ok"] is True and r["check"] in (True, None), (part, _key(r))
    assert all(r["check"] in (True, None) for r in raw["gemischt"])
    assert all(r["rules_ok"] is True for r in raw["regeln"])


def test_demo_size_holds_for_every_measured_timetable(raw):
    for part in ("rampe", "plaetze", "gemischt", "takt"):
        assert max(r["n"] for r in raw[part]) <= C.MAX_TRIPS
    assert min(r["n"] for r in raw["tag"]) > C.MAX_TRIPS and min(r["n"] for r in raw["tag2"]) > 150     # die Grenzmessungen liegen wirklich über der Demo-Größe


def test_bounds_are_ordered_and_the_electric_optimum_never_beats_the_diesel_bound(raw):
    for part in ("rampe", "plaetze", "takt", "tag", "tag2"):
        for r in raw[part]:
            if r["value"] is None:
                continue
            assert r["value"] >= r["diesel"], (part, _key(r))              # Batterie spart nie einen Bus gegenüber dem Dieselumlauf
            assert r["bound"] is not None and r["bound"] <= r["value"]
            assert r["value"] <= min(v for k, v in r["rules"].items() if k in RULES5 and v is not None), (part, _key(r))   # Löser nie schlechter als die beste Regel
            if r["status"] == "OPTIMAL":
                assert r["bound"] == r["value"], _key(r)               # bewiesen heißt: untere Schranke gleich Zielwert


def test_proven_zero_surcharge_cells_are_proven_not_dead_columns(raw):
    """Nullspalten: Aufschlag 0 steht nur dort, wo die Dieselschranke erreicht und damit bewiesen ist; und jede Ladeleistungs-Spalte und jede Batterie-Zeile hat irgendwo einen
    positiven Aufschlag (sonst liefe die Variante nie)."""
    rows = [r for r in raw["rampe"] if r["value"] is not None]
    for r in rows:
        if r["value"] == r["diesel"]:
            assert r["status"] == "OPTIMAL", _key(r)
    for p in C.RAMP_P:
        assert any(r["value"] > r["diesel"] for r in rows if r["p"] == p), p
    for c in (60, 80, 100):
        assert any(r["value"] > r["diesel"] for r in rows if r["c"] == c), c
    assert not any(r["value"] > r["diesel"] for r in rows if r["c"] == 120 and r["p"] == 40 and r["season"] == "Sommer")


def test_the_proven_optimum_is_monotone_in_battery_and_power(data):
    mono = data["regeln"]["opt_monotone"]
    assert mono["c"][0] == 0 and mono["p"][0] == 0
    assert mono["c"][1] >= 150 and mono["p"][1] >= 150


def test_rules_differ_pairwise_somewhere_on_the_large_series(data):
    big = data["regeln"]["grosse_reihe"]
    assert big["rows"] == 12800 and big["seeds"] == 200 and big["rejected"] == 0
    assert all(v > 0 for v in big["pair_differ"].values()), big["pair_differ"]       # jede Regel weicht von jeder anderen irgendwo ab (kein toter Zweig)
    # „Dieselplan, dann trennen“ ändert sich nie zu spät mit mehr Batterie oder Leistung: sein Dieselplan bleibt fest, nur das Trennen wird weniger
    assert data["regeln"]["grosse_reihe"]["nonmono"]["diesel_trennen"]["c"][0] == 0


def test_cap_model_with_many_places_equals_the_model_without_a_place_limit():
    """Kreuzprobe: 20 Plätze (< n Fahrten, also läuft das Modell MIT Platzgrenze) gegen unbegrenzt (Modell ohne Platzgrenze): bei beiderseits bewiesenen Fällen gleich."""
    compared = 0
    for seed, (c, p) in itertools.product(range(6), ((80, 20), (100, 10), (60, 40))):
        inst = S.generate(seed)
        a = X.solve(inst, E.Params(c, p, 1.0, "beide", 20), time_limit=20, workers=2)
        b = X.solve(inst, E.Params(c, p, 1.0, "beide", C.SLOTS_UNLIMITED), time_limit=20, workers=2)
        if a.proven and b.proven:
            assert a.value == b.value, (seed, c, p)
            compared += 1
    assert compared >= 12


def test_json_is_the_aggregate_of_the_raw_data(data, raw):
    """Die App-Tabelle (JSON) hat je Zelle 10 Seeds und stimmt mit einer frischen Auswertung der Rohdaten überein."""
    rampe = [dict(r) for r in raw["rampe"]]
    A.hull(rampe)
    fresh = A.ramp_table(rampe)
    assert fresh == data["rampe"]
    assert all(cell["n"] == 10 for block in data["rampe"].values() for cell in block.values())
    assert data["meta"]["rampe"]["rows"] == 640 and data["meta"]["rampe"]["rejected"] == 0
