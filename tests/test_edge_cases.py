"""Randfälle (DEMO-PLAYBOOK §12): eine Fahrt, zwei Fahrten, Fahrt allein nicht fahrbar, keine Anschlüsse, Gleichstand, inklusive Grenzen."""

import ebu_diesel as D
import ebu_energy as E
import ebu_exact as X
import ebu_rules as R
import ebu_scenario as S

ALL_RULES = ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen")


def test_single_trip():
    inst = S.make_instance([(360, 400, 0)], 10.0)
    assert D.diesel_plan(inst).buses == 1 and not inst.arcs
    assert X.solve(inst, E.Params(40, 0), time_limit=5, workers=1).value == 1
    assert {k: v.buses for k, v in R.all_rules(inst, E.Params(40, 0)).items()} == {k: 1 for k in ALL_RULES}


def test_exactly_two_trips_with_one_connection():
    inst = S.make_instance([(360, 400, 0), (410, 450, 1)], 10.0)
    assert D.diesel_plan(inst).buses == 1
    assert X.solve(inst, E.Params(40, 0), time_limit=5, workers=1).value == 1       # 26 kWh <= 36 nutzbar
    assert X.solve(inst, E.Params(28, 0), time_limit=5, workers=1).value == 2       # 26 > 25,2: getrennt


def test_a_trip_that_the_battery_cannot_drive_alone():
    inst = S.make_instance([(360, 400, 0), (410, 450, 1)], 10.0)
    prm = E.Params(14, 0)                                                              # nutzbar 12,6 < 13 kWh
    assert all(p is None for p in R.all_rules(inst, prm).values())
    assert X.solve(inst, prm, time_limit=5, workers=1).status == "TRIP_INFEASIBLE"


def test_usable_battery_bound_is_inclusive():
    inst = S.make_instance([(360, 400, 0)], 10.0)                                      # 13 kWh
    assert X.solve(inst, E.Params(14.5, 0), time_limit=5, workers=1).value == 1       # 14,5 − 1,45 = 13,05 >= 13
    assert X.solve(inst, E.Params(14.4, 0), time_limit=5, workers=1).status == "TRIP_INFEASIBLE"  # 12,96 < 13


def test_no_arcs_means_one_bus_per_trip():
    inst = S.make_instance([(360, 400, 0), (365, 405, 1), (370, 410, 0)], 10.0)
    assert not inst.arcs and D.diesel_plan(inst).buses == 3
    assert X.solve(inst, E.Params(100, 0), time_limit=5, workers=1).value == 3


def test_tie_break_changes_the_rule_on_a_hand_example():
    """Zwei volle Busse (gleicher Ladestand durch Laden bis C) stehen für Fahrt 2 bereit: „Einsatzreihenfolge“ nimmt den zuerst eingesetzten, „früh“ den mit der
    längsten Standzeit, „spät“ den mit der kürzesten."""
    inst = S.make_instance([(360, 380, 0), (362, 382, 0), (420, 440, 1), (421, 441, 1)], 6.0)
    prm = E.Params(40, 600)
    chains = {t: R.greedy(inst, prm, "soc_max", t).chains for t in R.TIES}
    assert chains["liste"] == ((0, 2), (1, 3))
    assert chains["frueh"] == ((0, 2), (1, 3))       # Bus 0 stand länger (endete um 380)
    assert chains["spaet"] == ((0, 3), (1, 2))       # Bus 1 (endete um 382) hat die kürzere Standzeit


def test_slot_limit_one_forbids_two_simultaneous_charges():
    inst = S.make_instance([(360, 400, 0), (365, 405, 0), (460, 500, 1), (470, 510, 1)], 10.0)
    prm = E.Params(40, 60, 1.0, "beide", 1)
    for rule in R.RULES:
        plan = R.greedy(inst, prm, rule)
        assert E.check_plan(inst, prm, plan)[0]
        assert max(E.peak_slots_used(inst, prm, plan.charged).values(), default=0) <= 1


def test_hybrid_with_a_budget_below_the_diesel_minimum_is_infeasible(mini):
    r = X.solve(mini, E.Params(28, 30), budget=D.diesel_plan(mini).buses - 1, time_limit=5, workers=1)
    assert r.status == "INFEASIBLE" and r.value is None


def test_hybrid_by_hand(mini):
    """C = 28 ohne Laden: kein Bus kann zwei Fahrten elektrisch fahren. Flotte 2 (= Dieselmindestflotte): beide Ketten Diesel. Flotte 3: ein Dieselbus mit
    zwei Fahrten und zwei Elektrobusse. Flotte 4: alle vier Fahrten elektrisch."""
    prm = E.Params(28, 0)
    assert X.solve(mini, prm, budget=2, time_limit=5, workers=1).value == 2
    r = X.solve(mini, prm, budget=3, time_limit=5, workers=1)
    assert r.value == 1 and E.check_plan(mini, prm, r.plan)[0]
    assert X.solve(mini, prm, budget=4, time_limit=5, workers=1).value == 0


def test_a_deadhead_costs_energy():
    """B → A nötig: Leerfahrt 10 km = 13 kWh zwischen zwei Fahrten à 13 kWh: 39 kWh > 36 kWh nutzbar bei C = 40, aber 39 <= 45 bei C = 50."""
    inst = S.make_instance([(360, 400, 0), (470, 510, 0)], 10.0)
    assert inst.arcs[0][2] == 10.0
    assert X.solve(inst, E.Params(40, 0), time_limit=5, workers=1).value == 2
    assert X.solve(inst, E.Params(50, 0), time_limit=5, workers=1).value == 1
