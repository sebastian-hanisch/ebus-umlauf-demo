"""Verdikte an von Hand gesetzten Werten (DEMO-PLAYBOOK §12): jede Zahl im Text und jede Schwelle der Art steht hier."""

import ebu_constants as C
import ebu_energy as E
import ebu_evaluation as ev
import ebu_exact as X


def _res(status="OPTIMAL", value=9, bound=None, plan=None):
    return X.ExactResult(status, value, value if bound is None and status == "OPTIMAL" else bound, plan, 1.0)


def test_surcharge_proven_with_surcharge_names_both_numbers():
    kind, text = ev.verdict_surcharge(7, _res(value=9))
    assert kind == "info" and "Aufschlag 2 Busse" in text and "9 Busse statt 7 Busse" in text and "bewiesen" in text


def test_surcharge_proven_zero_is_a_success():
    kind, text = ev.verdict_surcharge(7, _res(value=7))
    assert kind == "success" and "Kein Aufschlag" in text and "7 Busse" in text


def test_surcharge_one_bus_uses_the_singular():
    assert "Aufschlag 1 Bus:" in ev.verdict_surcharge(7, _res(value=8))[1]


def test_surcharge_not_proven_gives_an_interval_and_never_calls_it_optimal():
    kind, text = ev.verdict_surcharge(7, _res("FEASIBLE", value=11, bound=9))
    assert kind == "warning"
    assert "Nicht bewiesen" in text and "11 Busse sind erreicht" in text and "9 Busse sind bewiesen nötig" in text
    assert "zwischen 2 und 4 Bussen" in text and "kein Optimum" in text


def test_surcharge_not_proven_but_bounds_meet_is_an_info():
    kind, text = ev.verdict_surcharge(7, _res("FEASIBLE", value=9, bound=9))
    assert kind == "info" and "Aufschlag 2 Busse" in text and "Nicht bewiesen" not in text


def test_surcharge_without_solution_and_trip_infeasible():
    assert ev.verdict_surcharge(7, X.ExactResult("UNKNOWN", None, 7, None, 20.0))[0] == "warning"
    kind, text = ev.verdict_surcharge(7, X.ExactResult("TRIP_INFEASIBLE", None, None, None, 0.0))
    assert kind == "error" and "nicht einmal für eine einzelne Fahrt" in text
    assert ev.verdict_surcharge(7, X.ExactResult("INFEASIBLE", None, None, None, 0.0))[0] == "error"


def test_surcharge_bounds_are_clamped_at_zero():
    assert ev.surcharge_bounds(7, X.ExactResult("FEASIBLE", 9, 5, None, 1.0)) == (0, 2)
    assert ev.surcharge_bounds(7, X.ExactResult("UNKNOWN", None, None, None, 1.0)) == (0, None)


def test_rules_verdict_branches():
    plan = E.Plan(((0,),) * 11)
    kind, text = ev.verdict_rules("soc_max", plan, _res(value=9))
    assert kind == "warning" and "11 Busse" in text and "9 Busse" in text and "2 Busse zu viel" in text and "Ladestand max." in text
    kind, text = ev.verdict_rules("spaet", E.Plan(((0,),) * 9), _res(value=9))
    assert kind == "success" and "trifft das bewiesene Optimum" in text
    kind, text = ev.verdict_rules("spaet", E.Plan(((0,),) * 9), _res("FEASIBLE", value=9, bound=8))
    assert kind == "info" and "nicht weniger als 8 Busse" in text
    kind, text = ev.verdict_rules("spaet", E.Plan(((0,),) * 12), _res("FEASIBLE", value=9, bound=8))
    assert kind == "warning" and "nicht bewiesen" in text and "bis zu 3 Busse" in text
    assert ev.verdict_rules(None, None, _res())[0] == "warning"
    assert ev.verdict_rules("spaet", E.Plan(((0,),) * 9), X.ExactResult("UNKNOWN", None, 7, None, 1.0))[0] == "info"


def test_hybrid_verdict_names_fleet_and_diesel_buses():
    plan = E.Plan(((0,), (1,), (2,), (3,), (4,), (5,), (6,)), frozenset(), frozenset({0, 1, 2}))
    kind, text = ev.verdict_hybrid(7, 7, X.ExactResult("OPTIMAL", 3, 3, plan, 1.0))
    assert kind == "info" and "7 Bussen (Dieselmindestflotte 7) bleiben 3 Busse Diesel" in text and "4 fahren elektrisch" in text and "bewiesen" in text
    plan0 = E.Plan(((0,), (1,)), frozenset(), frozenset())
    kind, text = ev.verdict_hybrid(2, 2, X.ExactResult("OPTIMAL", 0, 0, plan0, 1.0))
    assert kind == "success" and "ganze Flotte elektrisch" in text
    kind, text = ev.verdict_hybrid(7, 8, X.ExactResult("FEASIBLE", 3, 2, plan, 1.0))
    assert "nicht bewiesen, mindestens 2 Dieselbusse nötig" in text
    assert ev.verdict_hybrid(7, 7, X.ExactResult("UNKNOWN", None, None, None, 1.0))[0] == "warning"


def test_slots_verdict_branches():
    one, two, many = _res(value=10), _res(value=8), _res(value=8)
    kind, text = ev.verdict_slots({1: one, 2: two, C.SLOTS_UNLIMITED: many}, 7)
    assert kind == "info" and "kostet 2 Busse mehr" in text and "10 Busse statt 8 Busse" in text
    kind, text = ev.verdict_slots({1: _res(value=8), 2: two, C.SLOTS_UNLIMITED: many}, 7)
    assert kind == "success" and "ändert hier nichts" in text
    kind, text = ev.verdict_slots({1: _res("FEASIBLE", value=10, bound=9), 2: two, C.SLOTS_UNLIMITED: many}, 7)
    assert kind == "warning" and "mindestens 9" in text
    kind, text = ev.verdict_slots({1: X.ExactResult("UNKNOWN", None, None, None, 1.0), 2: two, C.SLOTS_UNLIMITED: many}, 7)
    assert kind == "warning" and "kein Vergleich" in text
