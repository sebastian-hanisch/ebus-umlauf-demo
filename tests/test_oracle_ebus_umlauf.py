"""Orakel-Tests (DEMO-PLAYBOOK §12): der Umlauf mit Batteriegrenze gegen einen ANDEREN Rechenweg.

Orakel 1: vollständige Aufzählung aller Zerlegungen der Fahrten in Ketten (Mini-Instanzen bis 7 Fahrten) mit eigener, hier neu geschriebener Physik
(Verbrauch, Leerfahrt, lineares Laden, Reserve, Ladeplätze mit Teilmengen-Aufzählung der Ladeentscheidungen). Sie benutzt weder `ebu_energy` noch `ebu_exact`.
Orakel 2: Dieselumlauf = n − Matching gegen networkx (Hopcroft-Karp) und gegen die Aufzählung.
Orakel 3: Eigenschaftstests auf bewiesenen Paaren (mehr Batterie, mehr Ladeleistung, mehr Plätze, Lader an beiden Endhaltepunkten, Sommer statt Winter
dürfen nie mehr Busse brauchen).
Orakel 4: der Prüfer `check_plan` lehnt von Hand gebaute unzulässige Pläne ab."""

import itertools
import math
import random

import pytest

import ebu_constants as C
import ebu_diesel as D
import ebu_energy as E
import ebu_exact as X
import ebu_scenario as S

KWH_KM = 1.3


# ----------------------------------------------------------------------------------------------- Orakel: eigene Physik
def _gap_ok(inst, i, j):
    dht = 0 if inst.dest[i] == inst.orig[j] else inst.dh_min
    return inst.start[j] - inst.end[i] >= dht + inst.layover


def _chain_energy_ok(inst, chain, c, p, fw, chargers, charge_set=None):
    """Ladestand einer Kette in Fließkomma. charge_set=None: überall laden, wo es geht; sonst nur auf den Anschlüssen der Menge."""
    res = 0.1 * c
    e = lambda t: inst.dist[t] * KWH_KM * fw
    soc = c - e(chain[0])
    if soc < res - 1e-9:
        return False
    for a, b in zip(chain, chain[1:]):
        same = inst.dest[a] == inst.orig[b]
        dht = 0 if same else inst.dh_min
        soc -= 0.0 if same else inst.dh_km * KWH_KM * fw
        if soc < res - 1e-9:
            return False
        if _charge_possible(inst, a, b, p, chargers)[0] and (charge_set is None or (a, b) in charge_set):
            minutes = max(0, inst.start[b] - inst.end[a] - dht - inst.layover - 3)
            soc = min(c, soc + p * minutes / 60.0)
        soc -= e(b)
        if soc < res - 1e-9:
            return False
    return True


def _charge_possible(inst, a, b, p, chargers):
    """(möglich, Haltepunkt, Zeitraum): geladen wird am Ankunftspunkt der Fahrt a, sonst am Startpunkt der Fahrt b; Zeit muss übrig bleiben."""
    if p <= 0:
        return False, None, None
    has = lambda s: chargers == "beide" or s == 0
    u, v = inst.dest[a], inst.orig[b]
    dht = 0 if u == v else inst.dh_min
    if has(u):
        site, iv = u, (inst.end[a], inst.start[b] - dht)
    elif has(v):
        site, iv = v, (inst.end[a] + dht, inst.start[b])
    else:
        return False, None, None
    if inst.start[b] - inst.end[a] - dht - inst.layover - 3 <= 0:
        return False, None, None
    return True, site, (iv[0], max(iv[0] + 1, iv[1]))


def _slots_ok(inst, arcs, p, chargers, slots):
    per = {0: [], 1: []}
    for a, b in arcs:
        ok, site, iv = _charge_possible(inst, a, b, p, chargers)
        per[site].append(iv)
    for ivs in per.values():
        for t in [x for x, _ in ivs]:
            if sum(1 for b0, e0 in ivs if b0 <= t < e0) > slots:
                return False
    return True


def brute_min_buses(inst, c, p, fw, chargers, slots):
    """Kleinste Busanzahl: alle Zerlegungen in Ketten, je Zerlegung die Ladeentscheidungen aufgezählt, wenn Plätze knapp sind. None = unzulässig."""
    n = inst.n
    best = [n + 1]
    chains = []

    def feasible_partition():
        # Anschlüsse, auf denen geladen werden könnte
        cand = [(a, b) for ch in chains for a, b in zip(ch, ch[1:]) if _charge_possible(inst, a, b, p, chargers)[0]]
        if slots >= n:
            return all(_chain_energy_ok(inst, ch, c, p, fw, chargers) for ch in chains)
        for r in range(len(cand), -1, -1):  # mehr Laden ist nie schlechter: von allen abwärts
            for sub in itertools.combinations(cand, r):
                s = set(sub)
                if _slots_ok(inst, sub, p, chargers, slots) and all(_chain_energy_ok(inst, ch, c, p, fw, chargers, s) for ch in chains):
                    return True
        return False

    def rec(j):
        if len(chains) >= best[0]:
            return
        if j == n:
            if feasible_partition():
                best[0] = len(chains)
            return
        for ch in chains:
            if _gap_ok(inst, ch[-1], j):
                ch.append(j)
                if _chain_energy_ok(inst, ch, c, p, fw, chargers):   # Vorprüfung mit maximalem Laden (notwendig)
                    rec(j + 1)
                ch.pop()
        chains.append([j])
        if _chain_energy_ok(inst, chains[-1], c, p, fw, chargers):
            rec(j + 1)
        chains.pop()

    rec(0)
    return best[0] if best[0] <= n else None


def brute_min_diesel(inst, c, p, fw, chargers, budget):
    """Gemischte Flotte (Plätze unbegrenzt): wenigste Dieselbusse bei höchstens `budget` Bussen. None = unzulässig."""
    n = inst.n
    best = [n + 1]
    chains = []

    def rec(j):
        if j == n:
            if len(chains) <= budget:
                best[0] = min(best[0], sum(1 for ch in chains if not _chain_energy_ok(inst, ch, c, p, fw, chargers)))
            return
        for ch in chains:
            if _gap_ok(inst, ch[-1], j):
                ch.append(j)
                rec(j + 1)
                ch.pop()
        chains.append([j])
        rec(j + 1)
        chains.pop()

    rec(0)
    return best[0] if best[0] <= n else None


def mini_instance(rng, n_max=7):
    """Zufällige Mini-Instanz: 4 bis n_max Fahrten einer Linie, Strecke 4 bis 9 km, Fahrzeit 12 bis 27 min."""
    n = rng.randint(4, n_max)
    dist = rng.choice([4.0, 5.5, 7.5, 9.0])
    dur = rng.randint(12, 27)
    rows, t = [], 360
    for _ in range(n):
        t += rng.randint(1, 18)
        rows.append((t, t + dur, rng.randint(0, 1)))
    return S.make_instance(rows, dist, layover=rng.choice([3, 3, 5]))


def takt_instance(rng):
    """Mini-Takt: je Richtung 3 bis 4 Fahrten im Abstand von 10 bis 16 min, Fahrzeit 10 bis 14 min, Gegenrichtung versetzt (höchstens 7 Fahrten).
    Hier wird die Batterie knapp, und mehrere Busse wollen gleichzeitig am selben Haltepunkt laden: die Familie, an der die Ladeplatzgrenze etwas ändert."""
    h, dur, k = rng.randint(10, 16), rng.randint(10, 14), rng.randint(3, 4)
    off = rng.randint(0, h - 1)
    rows = [(360 + i * h, 360 + i * h + dur, 0) for i in range(k)] + [(360 + off + i * h, 360 + off + i * h + dur, 1) for i in range(k)]
    return S.make_instance(rows[:7], rng.choice([6.0, 7.5]), layover=3)


# ----------------------------------------------------------------------------------------------- Orakel 1: Löser gegen Aufzählung
def _draw_case(rng, family="zufall"):
    if family == "takt":
        return takt_instance(rng), rng.choice([14, 17, 20, 26]), rng.choice([30, 60, 120]), rng.choice([1.0, C.WINTER_FACTOR]), rng.choice(["beide", "nur A"])
    inst = mini_instance(rng)
    c = rng.choice([22, 28, 36, 50])
    p = rng.choice([0, 30, 90, 300])
    fw = rng.choice([1.0, C.WINTER_FACTOR])
    chargers = rng.choice(["beide", "nur A"])
    return inst, c, p, fw, chargers


@pytest.mark.parametrize("slots", [C.SLOTS_UNLIMITED, 1])
def test_solver_equals_enumeration_on_mini_instances(slots):
    rng = random.Random(1234 + slots)
    compared = infeasible = surcharge = binding = 0
    for family, count in (("zufall", 15), ("takt", 25)):
        for _ in range(count):
            inst, c, p, fw, chargers = _draw_case(rng, family)
            want = brute_min_buses(inst, c, p, fw, chargers, slots)
            prm = E.Params(c, p, fw, chargers, slots)
            got = X.solve(inst, prm, time_limit=10, workers=2)
            if want is None:
                infeasible += 1
                assert got.status in ("TRIP_INFEASIBLE", "INFEASIBLE")
                continue
            assert got.status == "OPTIMAL"
            assert got.value == want, (family, inst.start, inst.orig, c, p, fw, chargers, slots)
            ok, why = E.check_plan(inst, prm, got.plan)
            assert ok, why
            compared += 1
            surcharge += want > D.diesel_plan(inst).buses
            if slots < C.SLOTS_UNLIMITED:
                binding += want > brute_min_buses(inst, c, p, fw, chargers, C.SLOTS_UNLIMITED)
    assert compared >= 30, (compared, infeasible)            # genug Fälle haben eine Lösung (der Test ist keine leere Prüfung)
    assert surcharge >= 10, surcharge                         # und in vielen kostet die Batterie mindestens einen Bus
    if slots < C.SLOTS_UNLIMITED:
        assert binding >= 2, binding                          # und in einigen ändert die Platzgrenze das Optimum (sonst prüfte der Test sie nicht)


def test_enumeration_itself_on_a_hand_example():
    """Handrechnung: 3 Fahrten à 10 km (13 kWh), ohne Laden. Batterie 30 kWh, Reserve 3: nutzbar 27, zwei Fahrten (26) gehen, drei (39) nicht: 2 Busse.
    Batterie 40: nutzbar 36 < 39: 2 Busse. Batterie 50: nutzbar 45 >= 39, aber Fahrt 2 startet in A, Fahrt 1 endet in A: kein Leerweg: 1 Bus."""
    inst = S.make_instance([(360, 400, 0), (410, 450, 1), (460, 500, 0)], 10.0)
    # Fahrt 0: A->B, 1: B->A, 2: A->B; Anschlüsse 0->1 und 1->2 ohne Leerfahrt
    assert brute_min_buses(inst, 30, 0, 1.0, "beide", C.SLOTS_UNLIMITED) == 2
    assert brute_min_buses(inst, 40, 0, 1.0, "beide", C.SLOTS_UNLIMITED) == 2
    assert brute_min_buses(inst, 50, 0, 1.0, "beide", C.SLOTS_UNLIMITED) == 1


def test_solver_equals_enumeration_hybrid_fleet():
    rng = random.Random(99)
    compared = 0
    cases = [_draw_case(rng, family) for family in ("zufall", "takt") for _ in range(15)]
    for inst, c, p, fw, chargers in cases:
        d = D.diesel_plan(inst).buses
        for extra in (0, 1):
            prm = E.Params(c, p, fw, chargers, C.SLOTS_UNLIMITED)
            want = brute_min_diesel(inst, c, p, fw, chargers, d + extra)
            got = X.solve(inst, prm, budget=d + extra, time_limit=10, workers=2)
            assert got.status == "OPTIMAL"
            assert got.value == want, (d, extra, c, p, fw, chargers)
            assert E.check_plan(inst, prm, got.plan)[0]
            compared += 1
    assert compared == 60


# ----------------------------------------------------------------------------------------------- Orakel 2: Dieselbasis
def _networkx_min_buses(inst):
    nx = pytest.importorskip("networkx")
    g = nx.Graph()
    left = [("L", i) for i in range(inst.n)]
    g.add_nodes_from(left, bipartite=0)
    g.add_nodes_from([("R", i) for i in range(inst.n)], bipartite=1)
    for i in range(inst.n):
        for j in range(i + 1, inst.n):
            if _gap_ok(inst, i, j) and inst.start[j] - inst.end[i] <= C.MAX_IDLE_MIN:
                g.add_edge(("L", i), ("R", j))
    m = nx.bipartite.hopcroft_karp_matching(g, top_nodes=left)
    return inst.n - len(m) // 2


def test_diesel_base_equals_networkx_matching_on_generated_instances():
    for seed in range(12):
        for tt in C.TIMETABLES:
            inst = S.generate(seed, tt)
            assert D.diesel_plan(inst).buses == _networkx_min_buses(inst)


def test_diesel_base_equals_enumeration_and_unconstrained_solver():
    rng = random.Random(7)
    for _ in range(40):
        inst = mini_instance(rng)
        want = brute_min_buses(inst, 1e6, 0, 1.0, "beide", C.SLOTS_UNLIMITED)   # riesige Batterie: keine Energiegrenze
        assert D.diesel_plan(inst).buses == want
        assert X.solve(inst, E.Params(1e6, 0), time_limit=10, workers=2).value == want


def test_diesel_proof_is_checked_and_a_tampered_proof_is_rejected():
    inst = S.generate(1)
    plan = D.diesel_plan(inst)
    ok, _ = D.verify_diesel_proof(inst, plan)
    assert ok
    too_small = D.DieselPlan(plan.buses, plan.chains, plan.matching_size, frozenset(), plan.cover_right)
    assert D.verify_diesel_proof(inst, too_small)[0] is False
    merged = D.DieselPlan(plan.buses - 1, plan.chains[1:], plan.matching_size, plan.cover_left, plan.cover_right)
    assert D.verify_diesel_proof(inst, merged)[0] is False


# ----------------------------------------------------------------------------------------------- Orakel 3: Monotonie
def test_proven_optimum_is_monotone_in_battery_power_slots_chargers_and_season():
    rng = random.Random(2024)
    pairs = 0
    for _ in range(12):
        inst = mini_instance(rng, 8)

        def val(c, p, fw, ch, sl):
            r = X.solve(inst, E.Params(c, p, fw, ch, sl), time_limit=10, workers=2)
            return r.value if r.proven else (math.inf if r.status == "INFEASIBLE" else None)

        base = dict(c=30, p=60, fw=1.0, ch="nur A", sl=1)
        v0 = val(**base)
        for key, better in (("c", 45), ("p", 200), ("sl", 99), ("ch", "beide"), ("fw", 1.0)):
            weaker = dict(base)
            if key == "fw":
                weaker["fw"] = C.WINTER_FACTOR
                lo, hi = val(**base), val(**weaker)       # Sommer <= Winter
                better_v, worse_v = lo, hi
            else:
                stronger = dict(base)
                stronger[key] = better
                better_v, worse_v = val(**stronger), v0
            if better_v is None or worse_v is None:
                continue
            assert better_v <= worse_v, (key, better_v, worse_v)
            pairs += 1
    assert pairs >= 40


# ----------------------------------------------------------------------------------------------- Orakel 4: Prüfer
def test_checker_rejects_hand_built_infeasible_plans():
    inst = S.make_instance([(360, 400, 0), (410, 450, 1), (460, 500, 0)], 10.0)
    prm = E.Params(30, 0)
    assert E.check_plan(inst, prm, E.Plan(((0,), (1,), (2,))))[0]
    ok, why = E.check_plan(inst, prm, E.Plan(((0, 1, 2),)))      # 39 kWh > 27 kWh nutzbar
    assert not ok and "Reserve" in why
    assert not E.check_plan(inst, prm, E.Plan(((0, 1), (1, 2))))[0]   # Fahrt 1 doppelt
    ok, why = E.check_plan(inst, prm, E.Plan(((0, 2), (1,))))     # 13 + Leerfahrt 13 + 13 = 39 kWh > 27 kWh nutzbar
    assert not ok and "Reserve" in why
    assert E.check_plan(inst, E.Params(60, 0), E.Plan(((0, 2), (1,))))[0]   # Batterie 60: nutzbar 54
    # zeitlich unzulässiger Anschluss: Fahrt 2 vor Ende von Fahrt 1 ist kein Anschluss in umgekehrter Reihenfolge
    assert not E.check_plan(inst, prm, E.Plan(((1, 0), (2,))))[0]


def test_checker_rejects_a_slot_violation():
    # zwei Busse laden gleichzeitig am Haltepunkt B (beide enden dort um 400 und 405 und fahren um 460/470 wieder ab), ein Platz
    inst = S.make_instance([(360, 400, 0), (365, 405, 0), (460, 500, 1), (470, 510, 1)], 10.0)
    plan = E.Plan(((0, 2), (1, 3)), frozenset({(0, 2), (1, 3)}))
    assert E.check_plan(inst, E.Params(40, 60, 1.0, "beide", 2), plan)[0]
    ok, why = E.check_plan(inst, E.Params(40, 60, 1.0, "beide", 1), plan)
    assert not ok and "gleichzeitig" in why


def test_winter_at_zero_power_equals_summer_with_a_battery_scaled_by_the_winter_factor():
    """Ohne Laden skaliert der Winter alles gleich (Fahrten, Leerfahrten, Reserve als Anteil von C): Winter bei C kWh = Sommer bei C / 1,36 kWh.
    Gilt nur bei P = 0; mit Laden bleibt die Ladeleistung gleich und die Gleichung bricht."""
    rng = random.Random(31)
    equal = differ_with_charging = 0
    for _ in range(30):
        inst = mini_instance(rng)
        c = rng.choice([22, 28, 36, 50])
        w = brute_min_buses(inst, c, 0, C.WINTER_FACTOR, "beide", C.SLOTS_UNLIMITED)
        s = brute_min_buses(inst, c / C.WINTER_FACTOR, 0, 1.0, "beide", C.SLOTS_UNLIMITED)
        assert w == s, (inst.start, c)
        equal += 1
    for _ in range(40):
        inst = takt_instance(rng)
        c = rng.choice([17, 20, 26])
        if brute_min_buses(inst, c, 60, C.WINTER_FACTOR, "beide", C.SLOTS_UNLIMITED) != brute_min_buses(inst, c / C.WINTER_FACTOR, 60, 1.0, "beide", C.SLOTS_UNLIMITED):
            differ_with_charging += 1
    assert equal == 30
    assert differ_with_charging >= 1       # mit Laden gilt die Gleichung nicht (sonst wäre die Einschränkung auf P = 0 unnötig)
