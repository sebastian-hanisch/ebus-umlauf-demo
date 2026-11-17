"""Exakter Umlauf mit Batteriegrenze (CP-SAT): kleinste Busanzahl, optional mit Platzgrenze und optional als gemischte Flotte.

Modell: Boolesche Variable x_ij je zulässigem Anschluss, Start-Variable je Fahrt (neuer Bus), ganzzahliger Ladestand s_j bei Abfahrt der Fahrt j
(in 0,01 kWh; Verbrauch aufgerundet, Ladung abgerundet, die Rundung geht also nur zu Lasten des Modells: eine gefundene Lösung ist auch in Fließkomma
zulässig, `ebu_energy.check_plan` prüft das unabhängig). Je Anschluss: s_j <= s_i − e_i − Leerfahrt + Ladegewinn; s_i − e_i − Leerfahrt >= Reserve.
Mit begrenzten Ladeplätzen wird das Laden je Anschluss frei gewählt (Boolesche Variable c_ij) und belegt einen optionalen Zeitraum, je Haltepunkt höchstens
`slots` gleichzeitig (AddCumulative). Gemischte Flotte: je Kette Diesel oder Elektro; Diesel ohne Energiegrenze; Ziel: wenige Dieselbusse bei höchstens `budget` Bussen.

Ohne Beweis (Status FEASIBLE) steht die beste Zahl als OBERE Schranke da, nie als Optimum; die untere Schranke ist die des Lösers (aufgerundet) und mindestens
die Dieselschranke."""

import math
import time
from dataclasses import dataclass

import ebu_constants as C
from ebu_diesel import chains_from_next, diesel_plan
from ebu_energy import (Params, Plan, charge_gain, charge_interval, charge_site, deadhead_energy, full_charging, trip_energy)


@dataclass(frozen=True)
class ExactResult:
    status: str          # OPTIMAL, FEASIBLE, INFEASIBLE, TRIP_INFEASIBLE, UNKNOWN
    value: int | None    # Zielwert: Busse (rein elektrisch) bzw. Dieselbusse (gemischte Flotte)
    bound: int | None    # bewiesene untere Schranke des Zielwerts (ganzzahlig aufgerundet)
    plan: Plan | None
    seconds: float

    @property
    def proven(self) -> bool:
        return self.status == "OPTIMAL"


def _up(x: float) -> int:
    return int(math.ceil(x * C.SCALE - 1e-9))


def _dn(x: float) -> int:
    return int(math.floor(x * C.SCALE + 1e-9))


def solve(inst, prm: Params, *, budget: int | None = None, time_limit: float = C.EXACT_TIME_LIMIT_S, workers: int = C.EXACT_WORKERS,
          hint: Plan | None = None) -> ExactResult:
    """Kleinste Busanzahl (budget=None) bzw. kleinste Zahl Dieselbusse bei höchstens `budget` Bussen insgesamt."""
    from ortools.sat.python import cp_model
    t0 = time.time()
    n = inst.n
    hybrid = budget is not None
    e = trip_energy(inst, prm)
    Ci, Ri = int(round(prm.c * C.SCALE)), _up(prm.reserve)
    ei = [_up(x) for x in e]
    m = cp_model.CpModel()
    dsl = [m.NewBoolVar(f"d{i}") for i in range(n)] if hybrid else None
    soc = []
    for i in range(n):
        lo = ei[i] + Ri
        if lo > Ci:
            if not hybrid:
                return ExactResult("TRIP_INFEASIBLE", None, None, None, time.time() - t0)
            m.Add(dsl[i] == 1)
            lo = 0
        soc.append(m.NewIntVar(0 if hybrid else lo, Ci, f"s{i}"))
        if hybrid:
            m.Add(soc[i] >= lo).OnlyEnforceIf(dsl[i].Not())
    start = [m.NewBoolVar(f"y{i}") for i in range(n)]
    limited = prm.slots < n and prm.p > 0
    xs, chs = {}, {}
    outs = [[] for _ in range(n)]
    ins = [[] for _ in range(n)]
    per_site = {0: [], 1: []}
    gain_dh = {}
    for (i, j, dh_km, slack) in inst.arcs:
        site = charge_site(inst, prm, i, j)
        gain = _dn(charge_gain(prm, slack)) if site is not None else 0
        dhe = _up(deadhead_energy(dh_km, prm))
        if not hybrid and ei[i] + dhe + Ri > Ci:
            continue
        x = m.NewBoolVar(f"x{i}_{j}")
        xs[(i, j)] = x
        outs[i].append(x)
        ins[j].append(x)
        cond = [x, dsl[i].Not()] if hybrid else [x]
        if hybrid:
            m.Add(dsl[i] == dsl[j]).OnlyEnforceIf(x)
        m.Add(soc[i] - ei[i] - dhe >= Ri).OnlyEnforceIf(cond)
        gain_dh[(i, j)] = gain - dhe
        if gain > 0 and limited:
            ch = m.NewBoolVar(f"c{i}_{j}")
            m.AddImplication(ch, x)
            if hybrid:
                m.AddImplication(ch, dsl[i].Not())
            chs[(i, j)] = ch
            m.Add(soc[j] <= soc[i] - ei[i] - dhe + gain).OnlyEnforceIf(ch)
            m.Add(soc[j] <= soc[i] - ei[i] - dhe).OnlyEnforceIf(cond + [ch.Not()])
            bg, en = charge_interval(inst, i, j, site)
            iv = m.NewOptionalFixedSizeIntervalVar(bg, max(1, en - bg), ch, f"iv{i}_{j}")
            per_site[site].append(iv)
        else:
            m.Add(soc[j] <= soc[i] - ei[i] - dhe + gain).OnlyEnforceIf(cond)
    for j in range(n):
        m.Add(sum(ins[j]) + start[j] == 1)
        m.Add(sum(outs[j]) <= 1)
    for ivs in per_site.values():
        if ivs:
            m.AddCumulative(ivs, [1] * len(ivs), prm.slots)
    if hybrid:
        m.Add(sum(start) <= budget)
        ds = []
        for i in range(n):
            z = m.NewBoolVar(f"z{i}")
            m.AddBoolAnd([start[i], dsl[i]]).OnlyEnforceIf(z)
            m.AddBoolOr([start[i].Not(), dsl[i].Not()]).OnlyEnforceIf(z.Not())
            ds.append(z)
        m.Minimize(sum(ds))
    else:
        # gültiger Schnitt (Energiebilanz aller Busse): (C − R)·Busse + Ladegewinn der genutzten Anschlüsse >= Fahrtenergie + Leerfahrtenergie
        m.Add((Ci - Ri) * sum(start) + sum(gain_dh[k] * xs[k] for k in xs) >= sum(ei))
        m.Minimize(sum(start))
    if hint is not None and not hybrid:
        starts = {ch[0] for ch in hint.chains}
        nxt = {a: b for ch in hint.chains for a, b in zip(ch, ch[1:])}
        for j in range(n):
            m.AddHint(start[j], 1 if j in starts else 0)
        for (i, j), x in xs.items():
            m.AddHint(x, 1 if nxt.get(i) == j else 0)
        for (i, j), ch in chs.items():
            m.AddHint(ch, 1 if (i, j) in hint.charged else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = time_limit
    s.parameters.num_workers = workers
    s.parameters.random_seed = 1
    st = s.Solve(m)
    name = s.StatusName(st)
    secs = time.time() - t0
    base = diesel_plan(inst).buses
    bound_raw = s.BestObjectiveBound() if st in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN) else None
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        lb = None if bound_raw is None else int(math.ceil(bound_raw - 1e-6))
        return ExactResult("INFEASIBLE" if name == "INFEASIBLE" else "UNKNOWN", None, lb, None, secs)
    nxt = {i: j for (i, j), x in xs.items() if s.Value(x)}
    chains = tuple(chains_from_next(n, nxt))
    lb = int(math.ceil(s.BestObjectiveBound() - 1e-6))
    if not hybrid:
        lb = max(lb, base)
    if hybrid:
        diesel = frozenset(k for k, ch in enumerate(chains) if s.Value(dsl[ch[0]]))
        elec = [ch for k, ch in enumerate(chains) if k not in diesel]
        charged = (frozenset(a for a, ch in chs.items() if s.Value(ch)) if limited else full_charging(inst, prm, elec))
        plan = Plan(chains, charged, diesel)
        value = len(diesel)
    else:
        charged = frozenset(a for a, ch in chs.items() if s.Value(ch)) if limited else full_charging(inst, prm, chains)
        plan = Plan(chains, charged)
        value = len(chains)
    return ExactResult(name, value, min(lb, value), plan, secs)
