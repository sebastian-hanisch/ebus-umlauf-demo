"""Kern gegen Handrechnung (Mini-Instanz aus conftest.py): Anschlüsse, Dieselumlauf, Energie, Laden, Regeln, Prüfer, exakter Löser."""

import pytest

import ebu_constants as C
import ebu_diesel as D
import ebu_energy as E
import ebu_exact as X
import ebu_rules as R
import ebu_scenario as S


def test_arcs_by_hand(mini):
    assert [(i, j, dh, slack) for i, j, dh, slack in mini.arcs] == [(0, 3, 0.0, 27), (1, 2, 0.0, 7)]
    assert mini.dh_min == 24 and mini.layover == 3


def test_diesel_base_by_hand(mini):
    plan = D.diesel_plan(mini)
    assert plan.buses == 2 and plan.matching_size == 2
    assert sorted(plan.chains) == [(0, 3), (1, 2)]
    assert D.verify_diesel_proof(mini, plan)[0]
    assert plan.cover_size == 2 == mini.n - plan.buses


def test_energy_and_charging_by_hand(mini):
    prm = E.Params(28, 30)                       # nutzbar 28 − 2,8 = 25,2 kWh; 13 kWh je Fahrt
    assert E.trip_energy(mini, prm) == pytest.approx([13.0] * 4)
    assert E.charge_gain(prm, 27) == pytest.approx(30 * 24 / 60)     # (27 − 3 min) · 30 kW = 12 kWh
    assert E.charge_gain(prm, 7) == pytest.approx(30 * 4 / 60)       # (7 − 3) · 30 kW = 2 kWh
    assert E.charge_gain(prm, 3) == 0.0                              # nur das An-/Abstecken: nichts bleibt zum Laden
    assert E.charge_interval(mini, 0, 3, 1) == (400, 430)            # Platz am Haltepunkt B während der ganzen Wartezeit
    assert E.charge_interval(mini, 1, 2, 0) == (410, 420)
    assert E.chain_energy(mini, prm, (0, 3)) == pytest.approx(26.0)


@pytest.mark.parametrize("p,chargers,buses", [(0, "beide", 4), (30, "beide", 2), (30, "nur A", 3)])
def test_exact_solver_by_hand(mini, p, chargers, buses):
    """C = 28 kWh: ohne Laden reicht die Batterie für keine zwei Fahrten (26 > 25,2): 4 Busse. Mit 30 kW an beiden Haltepunkten gehen beide Ketten (2 Busse);
    nur am Haltepunkt A fehlt der Lader für die Kette (0,3) in B: 3 Busse."""
    prm = E.Params(28, p, 1.0, chargers)
    r = X.solve(mini, prm, time_limit=10, workers=1)
    assert r.proven and r.value == buses
    assert E.check_plan(mini, prm, r.plan)[0]


def test_all_rules_by_hand(mini):
    plans = R.all_rules(mini, E.Params(28, 0))
    assert {k: v.buses for k, v in plans.items()} == {"spaet": 4, "frueh": 4, "soc_max": 4, "soc_min": 4, "diesel_trennen": 4}
    plans = R.all_rules(mini, E.Params(28, 30))
    assert {k: v.buses for k, v in plans.items()} == {"spaet": 2, "frueh": 2, "soc_max": 2, "soc_min": 2, "diesel_trennen": 2}
    for plan in plans.values():
        assert E.check_plan(mini, E.Params(28, 30), plan)[0]
        assert plan.charged == frozenset({(0, 3), (1, 2)})


def test_with_a_large_battery_the_electric_plan_equals_the_diesel_plan(mini):
    prm = E.Params(60, 0)
    assert X.solve(mini, prm, time_limit=10, workers=1).value == D.diesel_plan(mini).buses == 2


def test_checker_accepts_exactly_the_hand_feasible_chains(mini):
    prm = E.Params(28, 30)
    assert E.check_plan(mini, prm, E.Plan(((0, 3), (1, 2)), frozenset({(0, 3), (1, 2)})))[0]
    assert not E.check_plan(mini, prm, E.Plan(((0, 3), (1, 2))))[0]            # ohne Laden reicht die Batterie nicht
    assert not E.check_plan(mini, prm, E.Plan(((0, 2), (1, 3))))[0]            # Anschlüsse gibt es nicht
    assert not E.check_plan(mini, prm, E.Plan(((0, 3), (1, 2)), frozenset({(0, 2)})))[0]


def test_generated_instances_stay_within_the_demo_size():
    sizes = [S.generate(seed).n for seed in range(3000)]
    assert max(sizes) <= C.MAX_TRIPS and min(sizes) >= 30
    assert S.generate(1, "takt").n <= C.MAX_TRIPS


def test_generator_is_deterministic_and_seed_dependent():
    assert S.generate(5) == S.generate(5)
    assert S.generate(5) != S.generate(6)


def test_takt_turnaround_rule_by_hand():
    assert S.takt_turnaround(32) == 5          # 10 % von 32 min = 3,2 → 4, aber mindestens 5 min
    assert S.takt_turnaround(60) == 6
    assert S.takt_turnaround(61) == 7          # aufgerundet
    inst = S.generate(0, "takt")
    assert inst.layover == S.takt_turnaround(inst.end[0] - inst.start[0])
