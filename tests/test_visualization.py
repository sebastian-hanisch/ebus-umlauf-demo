"""Figuren gegen die Daten: jeder Balken gehört zu einer Fahrt, jede Achse ist fest, Beschriftungen stimmen mit den Zahlen überein."""

import ebu_constants as C
import ebu_energy as E
import ebu_evaluation as ev
import ebu_visualization as V


def _traces(fig, name):
    return [t for t in fig.data if t.name == name]


def test_umlauf_has_one_bar_per_trip_with_the_right_position_and_length(mini):
    prm = E.Params(28, 30)
    plan = E.Plan(((0, 3), (1, 2)), frozenset({(0, 3), (1, 2)}))
    fig = V.build_umlauf(mini, prm, plan, "Test")
    (trips,) = _traces(fig, "Elektro-Fahrt")
    assert sorted(zip(trips.y, trips.base, trips.x)) == sorted([("Bus 1", 360, 40), ("Bus 1", 430, 40), ("Bus 2", 370, 40), ("Bus 2", 420, 40)])
    assert not _traces(fig, "Diesel-Fahrt")
    (charge,) = _traces(fig, "Laden (Platz belegt)")
    assert sorted(zip(charge.y, charge.base, charge.x)) == sorted([("Bus 1", 400, 30), ("Bus 2", 410, 10)])      # Platz belegt: ganze Wartezeit
    assert list(fig.layout.yaxis.categoryarray) == ["Bus 1", "Bus 2"]


def test_umlauf_colours_trips_by_the_soc_at_arrival(mini):
    prm = E.Params(28, 30)
    plan = E.Plan(((0, 3), (1, 2)), frozenset({(0, 3), (1, 2)}))
    (trips,) = _traces(V.build_umlauf(mini, prm, plan), "Elektro-Fahrt")
    colours = dict(zip(zip(trips.y, trips.base), trips.marker.color))
    # Bus 1: Fahrt 0 endet mit 28 − 13 = 15 kWh, Fahrt 3 mit 27 − 13 = 14 kWh (nach 12 kWh Laden bis höchstens 28: 15 + 12 = 27)
    assert abs(colours[("Bus 1", 360)] - 100 * 15 / 28) < 1e-9 and abs(colours[("Bus 1", 430)] - 100 * 14 / 28) < 1e-9


def test_diesel_buses_are_drawn_as_diesel_and_labelled(mini):
    plan = E.Plan(((0, 3), (1, 2)), frozenset(), frozenset({1}))
    fig = V.build_umlauf(mini, E.Params(28, 0), plan)
    assert [t.name for t in fig.data] == ["Elektro-Fahrt", "Diesel-Fahrt"]
    assert list(fig.layout.yaxis.categoryarray) == ["Bus 1", "Bus 2 (Diesel)"]
    assert list(fig.data[1].y) == ["Bus 2 (Diesel)"] * 2


def test_all_axes_are_fixed():
    fig = V.build_heatmap([[1, 2], [3, 4]], [0, 10], [60, 80], [["a", "b"], ["c", "d"]], "x", "y")
    assert fig.layout.xaxis.fixedrange and fig.layout.yaxis.fixedrange
    fig = V.build_rules(["a", "b"], [5, None], 4, True, 3)
    assert fig.layout.xaxis.fixedrange and fig.layout.yaxis.fixedrange


def test_heatmap_keeps_values_and_texts():
    fig = V.build_heatmap([[0.5, None], [2.0, 3.0]], C.RAMP_P[:2], C.RAMP_C[:2], [["a", ""], ["c", "d"]], "x", "y")
    h = fig.data[0]
    assert list(h.x) == ["0", "10"] and list(h.y) == ["60", "80"] and h.zmin == 0 and h.zmax == 3.0
    assert [list(r) for r in h.text] == [["a", ""], ["c", "d"]]


def test_rules_chart_shows_every_rule_and_marks_missing_solutions():
    fig = V.build_rules(["A", "B"], [7, None], 6, False, 5)
    bar = fig.data[0]
    assert list(bar.x) == [7, 0] and list(bar.text) == ["7", "keine Lösung"]
    notes = [a.text for a in fig.layout.annotations]
    assert "Dieselumlauf" in notes and "beste bekannte Zahl (nicht bewiesen)" in notes


def test_analysis_matches_independent_recomputation():
    s = ev.Settings(seed=2, c=60, p=20)
    a = ev.analyse(s)
    inst, prm = s.instance(), s.params()
    chain_kwh = max(sum(inst.dist[t] * 1.3 for t in ch) + sum(0.0 if inst.dest[x] == inst.orig[y] else inst.dh_km * 1.3 for x, y in zip(ch, ch[1:])) for ch in a.diesel.chains)
    assert abs(a.diesel_chain_kwh - chain_kwh) < 1e-9
    assert a.best[1].buses == min(p.buses for p in a.plans.values() if p is not None)
    assert all(ok for ok in a.plans_ok.values() if ok is not None)
    assert a.diesel.buses == 6 and inst.n == 42


def test_surcharge_ramp_live_covers_the_whole_grid_and_is_monotone_where_proven():
    s = ev.Settings(seed=2, c=80, p=20)
    ramp = ev.ramp_live(s, ev.analyse(s), (80, 100), (10, 20), time_limit=10)
    assert set(ramp) == {(80, 10), (80, 20), (100, 10), (100, 20)}
    for (c, p), r in ramp.items():
        assert r.value is not None
    proven = {k: r.value for k, r in ramp.items() if r.proven}
    for (c, p), v in proven.items():
        for (c2, p2), v2 in proven.items():
            if c2 >= c and p2 >= p:
                assert v2 <= v
