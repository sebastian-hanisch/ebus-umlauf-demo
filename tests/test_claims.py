"""Aussagen der README und der App gegen die Messreihe (DEMO-PLAYBOOK §4 und §11a).

Jede Zahl der README steht als Ausdruck in `tools/README.vorlage.md` und wird aus `data/messreihe.json` gebaut (`tools/readme_bauen.py`); die README muss genau das
Ergebnis des Baus sein. Die JSON-Datei muss genau das Ergebnis einer frischen Auswertung der Rohdaten sein. Darüber hinaus prüft diese Datei die Aussagen, die über
die Zahl hinausgehen („Rampe“, „nie weniger“, „bewiesen“), als Zählungen über das ganze Raster, und die Urteile der Presets."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import messreihe_auswertung as A  # noqa: E402
import readme_bauen as RB  # noqa: E402

import ebu_constants as C  # noqa: E402
import ebu_texte as T  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def d():
    return json.loads((ROOT / "data" / "messreihe.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def raw():
    return {part: A.load(part) for part in ("rampe", "plaetze", "gemischt", "takt")}


# ----------------------------------------------------------------------------------------------- README und JSON sind gebaut, nicht von Hand
def test_json_is_exactly_a_fresh_evaluation_of_the_raw_data(d):
    fresh = json.loads(json.dumps(A.build_data()))
    assert fresh == d


def test_readme_is_exactly_the_build_of_template_and_data():
    assert README == RB.build(RB.current_test_count())


def test_readme_test_count_equals_the_collected_tests():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")], capture_output=True, text=True, cwd=ROOT).stdout
    collected = int(re.search(r"(\d+) tests? collected", out).group(1))
    assert f"{collected} Tests" in README, collected


def test_app_texts_are_in_the_readme(d):
    """Zwei Fassungen desselben Textes (App und README) werden verglichen, nicht von Hand synchron gehalten."""
    assert T.regeln_markdown(d) in README and T.grenzen_markdown(d) in README


# ----------------------------------------------------------------------------------------------- Rampe
def _means(d, block):
    return {(int(c), int(p)): v["ub_mean"] for key, cell in d["rampe"].items() if key == block for k, v in cell.items() for c, p in [k.split("|")]}


@pytest.mark.parametrize("block", ["Sommer|beide", "Winter|beide", "Sommer|nur A", "Winter|nur A"])
def test_ramp_never_increases_with_battery_or_power(d, block):
    m = _means(d, block)
    for p in C.RAMP_P:
        col = [m[(c, p)] for c in C.RAMP_C]
        assert all(a >= b for a, b in zip(col, col[1:])), (block, p, col)
    for c in C.RAMP_C:
        row = [m[(c, p)] for p in C.RAMP_P]
        assert all(a >= b for a, b in zip(row, row[1:])), (block, c, row)


def test_ramp_falls_step_by_step_in_the_shown_row_and_column(d):
    m = _means(d, "Sommer|beide")
    row = [m[(60, p)] for p in C.RAMP_P]            # C = 60 kWh: jede Stufe der Ladeleistung senkt den Aufschlag
    assert all(a > b for a, b in zip(row, row[1:])), row
    col = [m[(c, 0)] for c in C.RAMP_C[:3]]         # P = 0: jede der ersten beiden Stufen der Batterie senkt ihn (die letzte Stufe geht bei 0 auf 0)
    assert all(a > b for a, b in zip(col, col[1:])), col
    assert all(m[(120, p)] == 0 for p in C.RAMP_P)  # und am Ende der Rampe ist er 0
    assert all(d["rampe"]["Sommer|beide"][f"120|{p}"]["proven"] == 10 for p in C.RAMP_P)   # beweisen alle zehn Fahrpläne


def test_ramp_cells_without_charging_are_often_unproven(d):
    cell = d["rampe"]["Sommer|beide"]["60|0"]
    assert cell["proven"] < cell["n"]                # die README sagt „ohne Laden bleibt der Beweis oft aus“


def test_ramp_cells_with_charging_in_summer_are_all_proven(d):
    for p in (10, 20, 40):
        for c in C.RAMP_C:
            cell = d["rampe"]["Sommer|beide"][f"{c}|{p}"]
            assert cell["proven"] == cell["n"], (c, p)


def test_winter_never_costs_less_than_summer_and_costs_more_in_most_cells(d, raw):
    w = d["fakten"]["winter"]
    assert w["cells"] == 32 and w["smaller"] == 0 and w["larger"] >= 20 and w["larger"] <= w["cells"]
    for ch in ("beide", "nur A"):                                  # nachgerechnet aus der Tabelle der App (Mittel je Zelle)
        larger = sum(1 for k, s in d["rampe"][f"Sommer|{ch}"].items() if d["rampe"][f"Winter|{ch}"][k]["ub_mean"] > s["ub_mean"] + 1e-9)
        assert larger >= 8


# ----------------------------------------------------------------------------------------------- Kettenenergie
def test_chain_energy_condition_is_sufficient_and_not_necessary(d):
    k = d["fakten"]["kettenenergie"]
    assert k["sufficient"] > 0 and k["sufficient_zero"] == k["sufficient"] == k["sufficient_proven_zero"]    # reicht die Batterie für jede Dieselkette: Aufschlag 0, bewiesen
    assert k["insufficient_zero_proven"] > 0                                                                  # nicht notwendig: auch ohne ausreichende Batterie kann er 0 sein
    assert k["insufficient_positive"] + k["insufficient_zero_proven"] <= k["insufficient"]


# ----------------------------------------------------------------------------------------------- Lader, Plätze
def test_chargers_only_at_a_never_needs_fewer_buses(d):
    f = d["fakten"]["lader"]
    assert f["better"] == 0 and f["worse"] > 0 and f["worse"] + f["same"] + f["better"] == f["pairs"]
    assert f["mean_b"] > f["mean_a"]


def test_slots_never_help_less_places_never_need_fewer_buses(d):
    for key in ("plaetze_1", "plaetze_2"):
        f = d["fakten"][key]
        assert f["better"] == 0 and f["worse"] + f["same"] == f["pairs"]
    assert d["fakten"]["plaetze_1"]["worse"] > 0
    one, two = d["fakten"]["plaetze_1"], d["fakten"]["plaetze_2"]
    assert one["mean_b"] - one["mean_a"] >= two["mean_b"] - two["mean_a"]       # weniger Plätze kosten mehr


# ----------------------------------------------------------------------------------------------- Regeln
def test_rules_best_of_five_hits_the_optimum_in_a_minority_of_rows(d):
    b = d["regeln"]["best_of"]
    assert b["hits"] / b["of"] < 0.25 and b["of"] == d["regeln"]["positive_proven"]


def test_diesel_split_is_the_worst_rule_and_never_optimal(d):
    pr = d["regeln"]["per_rule"]
    assert pr["diesel_trennen"]["hits"] == 0
    assert all(pr["diesel_trennen"]["mean_extra"] > pr[k]["mean_extra"] for k in ("spaet", "frueh", "soc_max", "soc_min"))


def test_rules_are_never_better_than_the_proven_optimum_in_every_proven_row(raw):
    rows = [r for r in raw["rampe"] if r["status"] == "OPTIMAL"]
    assert len(rows) > 400
    for r in rows:
        assert all(v >= r["value"] for k, v in r["rules"].items() if v is not None), r


def test_diesel_split_never_gets_worse_with_more_battery_or_power(d):
    big = d["regeln"]["grosse_reihe"]["nonmono"]["diesel_trennen"]
    assert big["c"][0] == 0 and big["p"][0] == 0 and big["c"][1] == big["p"][1] == 9600


def test_rule_example_is_reproduced_live(d):
    """Das Beispiel der README (Zufalls-Seed, Jahreszeit, Batterie): die Regel „Spät“ und das bewiesene Optimum, live neu gerechnet."""
    import ebu_energy as E
    import ebu_exact as X
    import ebu_rules as R
    import ebu_scenario as S
    ex = d["regeln"]["grosse_reihe"]["examples_in_sweep"]["spaet|c"]
    inst = S.generate(ex["seed"])
    fw = C.WINTER_FACTOR if ex["season"] == "Winter" else 1.0
    for c, want_rule, want_opt in ((ex["c_from"], ex["buses_from"], ex["opt_from"]), (ex["c_to"], ex["buses_to"], ex["opt_to"])):
        prm = E.Params(c, ex["p_from"], fw, ex["chargers"])
        assert R.greedy(inst, prm, "spaet").buses == want_rule
        r = X.solve(inst, prm, time_limit=30, workers=2)
        assert r.proven and r.value == want_opt
    assert ex["buses_to"] > ex["buses_from"] and ex["opt_to"] <= ex["opt_from"]


def test_tie_break_changes_few_rows(d):
    g = d["regeln"]["grosse_reihe"]
    assert 0 < g["tie_differ"] < 0.02 * g["tie_rows"]


# ----------------------------------------------------------------------------------------------- gemischte Flotte, Takt, Beweis, Hülle
def test_hybrid_one_reserve_bus_never_adds_diesel_buses(raw):
    by = {}
    for r in raw["gemischt"]:
        if r["diesel_buses"] is not None and r["status"] == "OPTIMAL":
            by.setdefault((r["seed"], r["season"], r["c"], r["p"]), {})[r["reserve_buses"]] = r["diesel_buses"]
    pairs = [v for v in by.values() if len(v) == 2]
    assert len(pairs) > 80 and all(v[1] <= v[0] for v in pairs)


def test_hybrid_larger_battery_and_power_never_add_diesel_buses_in_the_means(d):
    g = d["gemischt"]
    for season in ("Sommer", "Winter"):
        for rb in (0, 1):
            for p in (0, 20):
                m = [g[f"{season}|{c}|{p}|{rb}"]["mean"] for c in (60, 80, 100)]
                assert all(a >= b - 1e-9 for a, b in zip(m, m[1:])), (season, rb, p, m)


def test_takt_surcharge_is_larger_than_in_the_generator_timetables_in_most_cells(d):
    cmp = d["fakten"]["takt_gegen_zufall"]
    larger = sum(1 for v in cmp.values() if v["takt"] > v["zufall"])
    assert larger >= 12 and len(cmp) == 18, (larger, len(cmp))


def test_proof_counts_are_consistent(d):
    z = d["fakten"]["zeit"]
    assert z["proven_under_1s"] <= z["proven_under_5s"] <= z["proven_rows"] <= z["rows"]
    assert z["proven_median"] < 1.0 and z["median"] < 1.0
    for part in ("rampe", "plaetze", "takt"):
        assert d["meta"][part]["hull_improved"] == 0                                              # die Hülle verbesserte keine obere Schranke ...
        assert 0 <= d["meta"][part]["proven_hull"] - d["meta"][part]["proven_raw"] <= 2           # ... und machte höchstens zwei Zellen durch untere Schranken beweisbar


def test_demo_size_boundary_is_measured_not_assumed(d):
    assert d["tag"]["n_min"] > C.MAX_TRIPS and d["tag2"]["n_min"] > C.MAX_TRIPS
    assert d["tag"]["gap_max"] >= 0 and d["tag2"]["positive"] > 0
    assert d["tag2"]["positive_proven"] <= d["tag2"]["positive"]


def test_the_oracle_scratch_run_found_no_deviation():
    o = json.loads((ROOT / "tools" / "messdaten" / "oracle_scratch.json").read_text(encoding="utf-8"))
    assert sum(v["verglichen"] for v in o["elektro"].values()) >= 800 and sum(v["verglichen"] for v in o["gemischt"].values()) >= 500
    assert all(v["abweichungen"] == 0 for v in list(o["elektro"].values()) + list(o["gemischt"].values()))
    assert sum(v["platzgrenze_wirkt"] for v in o["elektro"].values()) >= 5


# ----------------------------------------------------------------------------------------------- Presets: erwartetes Urteil je Preset (live gerechnet)
# Preset → (Dieselumlauf, Elektro-Umlauf bewiesen, beste Regel, Text im Hilfetext)
PRESET_EXPECT = {
    "Sommer, 60 kWh, 10 kW": (6, 8, 9, "Der Dieselumlauf braucht 6 Busse, der Elektro-Umlauf 8, die beste einfache Regel 9"),
    "Ohne Laden, 100 kWh": (6, 7, 9, "Dieselumlauf 6 Busse, Elektro-Umlauf 7, die beste einfache Regel 9"),
    "Winter, nur ein Lader": (6, 8, 11, "Dieselumlauf 6, Elektro-Umlauf 8, die beste einfache Regel 11"),
    "Ein Ladeplatz am Endhaltepunkt": (6, 7, 9, "Elektro-Umlauf 7 Busse statt 6 bei unbegrenzten Plätzen (Dieselumlauf 6)"),
    "Gemischte Flotte im Winter": (6, 8, 10, "Die Flotte darf höchstens 7 Busse haben (Dieselmindestflotte 6 plus 1); 2 davon bleiben Diesel"),
    "Gleichmäßiger Takt": (5, 7, 9, "Dieselumlauf 5 Busse, Elektro-Umlauf 7, die beste einfache Regel 9"),
    "Regel verschlechtert sich mit mehr Batterie": (6, 7, 8, "Die Regel „Spät“ braucht 10 Busse, bei 100 kWh nur 8, während das Optimum von 8 auf 7 sinkt"),
}


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_verdict_matches_its_help_text(name):
    import ebu_evaluation as ev
    diesel, opt, rule, phrase = PRESET_EXPECT[name]
    assert phrase in C.PRESET_HELP[name]
    s = ev.Settings(**C.PRESETS[name])
    a = ev.analyse(s)
    r = ev.solve_exact(s, a, 30)
    assert a.diesel.buses == diesel and r.proven and r.value == opt and a.best[1].buses == rule, (name, a.diesel.buses, r.value, a.best[1].buses)
    kind, text = ev.verdict_surcharge(a.diesel.buses, r)
    assert kind == ("success" if opt == diesel else "info") and ("bewiesen" in text)


def test_preset_one_place_costs_exactly_one_bus_against_unlimited_places():
    import ebu_evaluation as ev
    s = ev.Settings(**C.PRESETS["Ein Ladeplatz am Endhaltepunkt"])
    res = ev.slots_live(s, ev.analyse(s), time_limit=30)
    assert (res[1].value, res[2].value, res[C.SLOTS_UNLIMITED].value) == (7, 6, 6) and all(r.proven for r in res.values())
    kind, text = ev.verdict_slots(res, 6)
    assert kind == "info" and "kostet 1 Bus mehr" in text and "7 Busse statt 6 Busse" in text


def test_preset_hybrid_fleet_numbers():
    import ebu_evaluation as ev
    got = {}
    for rb in (0, 1, 2):
        s = ev.Settings(**{**C.PRESETS["Gemischte Flotte im Winter"], "reserve_buses": rb})
        h = ev.solve_hybrid(s, ev.analyse(s), 30)
        assert h.proven
        got[rb] = h.value
    assert got == {0: 6, 1: 2, 2: 0}
    kind, text = ev.verdict_hybrid(6, 7, ev.solve_hybrid(ev.Settings(**C.PRESETS["Gemischte Flotte im Winter"]), ev.analyse(ev.Settings(**C.PRESETS["Gemischte Flotte im Winter"])), 30))
    assert kind == "info" and "bleiben 2 Busse Diesel" in text and "5 fahren elektrisch" in text


def test_preset_rule_gets_worse_with_a_larger_battery_while_the_optimum_improves():
    import ebu_energy as E
    import ebu_exact as X
    import ebu_rules as R
    import ebu_scenario as S
    p = C.PRESETS["Regel verschlechtert sich mit mehr Batterie"]
    inst = S.generate(p["seed"])
    got = {}
    for c in (100, 120):
        prm = E.Params(c, p["p"], C.WINTER_FACTOR, "beide")
        r = X.solve(inst, prm, time_limit=30, workers=2)
        assert r.proven
        got[c] = (R.greedy(inst, prm, "spaet").buses, r.value)
    assert got == {100: (8, 8), 120: (10, 7)}


def test_hybrid_live_calculation_uses_the_places_of_the_sidebar():
    """Kernfrage 4 rechnet mit der Platzzahl der Seitenleiste (Befund der Aussagenprüfung: Text und Code widersprachen sich)."""
    import ebu_energy as E
    import ebu_evaluation as ev
    base = dict(seed=2, c=60, p=40, season="Sommer", chargers="beide", reserve_buses=0)
    got = {}
    for slots in (C.SLOTS_UNLIMITED, 1):
        s = ev.Settings(**base, slots=slots)
        a = ev.analyse(s)
        h = ev.solve_hybrid(s, a, 30)
        assert h.proven and E.check_plan(a.inst, a.prm, h.plan)[0]
        got[slots] = h.value
    assert got == {C.SLOTS_UNLIMITED: 0, 1: 2}


def test_winter_and_charger_facts_exclude_forced_results(d):
    w = d["fakten"]["winter"]
    assert w["fully_proven_cells"] > 0 and w["fully_proven_smaller"] == 0 and 0 < w["fully_proven_larger"] <= w["fully_proven_cells"]
    assert d["fakten"]["lader_ohne_laden"] == 37 and d["fakten"]["lader"]["pairs"] == 225       # Paare mit P = 0 stehen nicht in der Lader-Zählung
