"""Szenario → Auswertung: Einstellungen, Analyse (Dieselbasis, Regeln), Rampe und Ladeplätze live, Messreihe laden, Verdikte als reine Funktionen."""

import json
from dataclasses import dataclass
from pathlib import Path

import ebu_constants as C
import ebu_energy as E
import ebu_exact as X
import ebu_rules as R
import ebu_scenario as S
from ebu_diesel import DieselPlan, diesel_plan

DATA_FILE = Path(__file__).resolve().parent / "data" / "messreihe.json"


@dataclass(frozen=True)
class Settings:
    """Alle Regler der Seitenleiste. Immer mit Schlüsselwörtern aufrufen (ein eingefügtes Feld verschob früher still Werte in anderen Demos)."""
    seed: int = C.DEFAULT_SEED
    c: int = C.PRESETS[C.DEFAULT_PRESET]["c"]
    p: int = C.PRESETS[C.DEFAULT_PRESET]["p"]
    season: str = C.PRESETS[C.DEFAULT_PRESET]["season"]
    chargers: str = C.PRESETS[C.DEFAULT_PRESET]["chargers"]
    slots: int = C.PRESETS[C.DEFAULT_PRESET]["slots"]
    reserve_buses: int = C.PRESETS[C.DEFAULT_PRESET]["reserve_buses"]
    timetable: str = C.PRESETS[C.DEFAULT_PRESET]["timetable"]

    def params(self) -> E.Params:
        return E.Params(float(self.c), float(self.p), C.WINTER_FACTOR if self.season == "Winter" else 1.0, self.chargers, self.slots)

    def instance(self) -> S.Instance:
        return S.generate(self.seed, self.timetable)


@dataclass(frozen=True)
class Analysis:
    inst: S.Instance
    prm: E.Params
    diesel: DieselPlan
    plans: dict            # Regel → Plan oder None
    plans_ok: dict         # Regel → vom Prüfer angenommen
    best: tuple | None     # (Regelname, Plan) mit den wenigsten Bussen
    diesel_chain_kwh: float  # Energie der energiereichsten Kette des Dieselumlaufs (Fahrten plus Leerfahrten, ohne Laden)
    ties: dict             # Gleichstandsbruch → Busse der Regel „Ladestand max.“


def analyse(settings: Settings) -> Analysis:
    inst, prm = settings.instance(), settings.params()
    diesel = diesel_plan(inst)
    plans = R.all_rules(inst, prm)
    ok = {k: (None if p is None else E.check_plan(inst, prm, p)[0]) for k, p in plans.items()}
    ties = {}
    for t in R.TIES:
        pl = R.greedy(inst, prm, "soc_max", t)
        ties[t] = None if pl is None else pl.buses
    kwh = max(E.chain_energy(inst, prm, ch) for ch in diesel.chains)
    return Analysis(inst, prm, diesel, plans, ok, R.best_rule(plans), kwh, ties)


def solve_exact(settings: Settings, a: Analysis, time_limit: float | None = None) -> X.ExactResult:
    return X.solve(a.inst, a.prm, time_limit=C.EXACT_TIME_LIMIT_S if time_limit is None else time_limit, hint=None if a.best is None else a.best[1])


def solve_hybrid(settings: Settings, a: Analysis, time_limit: float = 10.0) -> X.ExactResult:
    return X.solve(a.inst, a.prm, budget=a.diesel.buses + settings.reserve_buses, time_limit=time_limit)


def surcharge_bounds(diesel_buses: int, res: X.ExactResult):
    """(untere, obere) Schranke des Aufschlags in Bussen; obere None ohne Lösung. Aufschlag = Elektro-Umlauf minus Dieselumlauf."""
    lo = 0 if res.bound is None else max(0, res.bound - diesel_buses)
    hi = None if res.value is None else res.value - diesel_buses
    return lo, hi


def ramp_live(settings: Settings, a: Analysis, c_values=C.RAMP_C, p_values=C.RAMP_P, time_limit: float = C.RAMP_TIME_LIMIT_S) -> dict:
    """Optimum je Zelle (Batterie, Ladeleistung) auf DIESEM Fahrplan, übrige Einstellungen wie im Szenario."""
    out = {}
    for c in c_values:
        for p in p_values:
            prm = E.Params(float(c), float(p), a.prm.fw, a.prm.chargers, a.prm.slots)
            best = R.best_rule(R.all_rules(a.inst, prm))
            out[(c, p)] = X.solve(a.inst, prm, time_limit=time_limit, hint=None if best is None else best[1])
    return out


def slots_live(settings: Settings, a: Analysis, time_limit: float = C.RAMP_TIME_LIMIT_S) -> dict:
    """Optimum für 1, 2 und unbegrenzt viele Ladeplätze je Endhaltepunkt bei sonst gleichem Szenario."""
    out = {}
    for sl in (1, 2, C.SLOTS_UNLIMITED):
        prm = E.Params(a.prm.c, a.prm.p, a.prm.fw, a.prm.chargers, sl)
        best = R.best_rule(R.all_rules(a.inst, prm))
        out[sl] = X.solve(a.inst, prm, time_limit=time_limit, hint=None if best is None else best[1])
    return out


def load_messreihe() -> dict | None:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ----------------------------------------------------------------------------------------------- Verdikte (reine Funktionen)
def _bus(n: int) -> str:
    return "1 Bus" if n == 1 else f"{n} Busse"


def verdict_surcharge(diesel_buses: int, res: X.ExactResult):
    """Kernaussage zum Aufschlag gegenüber dem Dieselumlauf. Rückgabe (Streamlit-Art, Text)."""
    if res.status == "TRIP_INFEASIBLE":
        return "error", "Die Batterie reicht nicht einmal für eine einzelne Fahrt samt Reserve: Es gibt keinen Elektro-Umlauf."
    if res.status == "INFEASIBLE":
        return "error", "Mit diesen Einstellungen gibt es keinen zulässigen Elektro-Umlauf."
    if res.value is None:
        return "warning", f"Das Zeitlimit von {C.EXACT_TIME_LIMIT_S:.0f} s reichte nicht für eine Lösung; der Dieselumlauf braucht {_bus(diesel_buses)}."
    lo, hi = surcharge_bounds(diesel_buses, res)
    if res.proven:
        if hi == 0:
            return "success", f"Kein Aufschlag: Der Elektro-Umlauf kommt mit denselben {_bus(diesel_buses)} aus wie der Dieselumlauf (bewiesen)."
        return "info", f"Aufschlag {_bus(hi)}: {_bus(res.value)} statt {_bus(diesel_buses)} (bewiesen: weniger gehen nicht)."
    if lo == hi:
        return "info", f"Aufschlag {_bus(hi)} ({_bus(res.value)} statt {_bus(diesel_buses)})."
    return "warning", (f"Nicht bewiesen: {_bus(res.value)} sind erreicht (obere Schranke), {_bus(res.bound)} sind bewiesen nötig. Der Aufschlag liegt zwischen "
                       f"{lo} und {hi} {'Bus' if hi == 1 else 'Bussen'}; die Zahl {res.value} ist kein Optimum.")


def verdict_rules(best_name, best_plan, res: X.ExactResult):
    """Wie weit liegt die beste einfache Regel vom Optimum? (gegen das bewiesene Optimum nur, wenn bewiesen)"""
    if best_plan is None:
        return "warning", "Keine der Regeln findet einen Umlauf (eine Fahrt ist allein nicht fahrbar)."
    label = R.RULE_LABELS[best_name]
    if res.value is None:
        return "info", f"Beste einfache Regel: {label} mit {_bus(best_plan.buses)}; ohne Lösung des exakten Verfahrens kein Vergleich."
    gap = best_plan.buses - res.value
    if res.proven:
        if gap == 0:
            return "success", f"Die beste einfache Regel ({label}) trifft das bewiesene Optimum: {_bus(best_plan.buses)}."
        return "warning", f"Die beste einfache Regel ({label}) braucht {_bus(best_plan.buses)}, das bewiesene Optimum {_bus(res.value)}: {_bus(gap)} zu viel."
    if gap == 0:
        return "info", f"Die beste einfache Regel ({label}) erreicht mit {_bus(best_plan.buses)} dieselbe Zahl wie das exakte Verfahren; bewiesen ist nur: nicht weniger als {_bus(res.bound)}."
    return "warning", (f"Die beste einfache Regel ({label}) braucht {_bus(best_plan.buses)}; das exakte Verfahren hat {_bus(res.value)} gefunden (obere Schranke, "
                       f"nicht bewiesen): bis zu {_bus(gap)} Unterschied.")


def verdict_hybrid(diesel_buses: int, fleet: int, res: X.ExactResult):
    """Gemischte Flotte: wie viele Dieselbusse bleiben bei höchstens `fleet` Bussen insgesamt?"""
    if res.value is None:
        return "warning", f"Kein Ergebnis im Zeitlimit (Flottengröße {fleet})."
    elec = res.plan.buses - res.value   # Busse insgesamt minus Dieselbusse
    tail = "bewiesen: weniger Dieselbusse gehen bei dieser Flottengröße nicht" if res.proven else f"nicht bewiesen, mindestens {res.bound} Dieselbusse nötig"
    if res.value == 0:
        return "success", f"Bei einer Flottengröße von {fleet} Bussen (Dieselmindestflotte {diesel_buses}) kann die ganze Flotte elektrisch fahren ({tail})."
    return "info", (f"Bei einer Flottengröße von {fleet} Bussen (Dieselmindestflotte {diesel_buses}) bleiben {_bus(res.value)} Diesel; "
                    f"{elec} fahren elektrisch ({tail}).")


def verdict_slots(results: dict, diesel_buses: int):
    """Vergleich 1 / 2 / unbegrenzt Ladeplätze. `results`: {Plätze: ExactResult}; nur bewiesene Zahlen werden als Unterschied gewertet."""
    one, many = results[1], results[C.SLOTS_UNLIMITED]
    if one.value is None or many.value is None:
        return "warning", "Mindestens eine der Rechnungen fand im Zeitlimit keine Lösung: kein Vergleich möglich."
    if not (one.proven and many.proven):
        return "warning", (f"Nicht in allen Fällen bewiesen: ein Platz {one.value} Busse (obere Schranke, bewiesen mindestens {one.bound}), "
                           f"unbegrenzt {many.value} (bewiesen mindestens {many.bound}).")
    gap = one.value - many.value
    if gap == 0:
        return "success", f"Die Platzzahl ändert hier nichts: auch mit einem Ladeplatz je Endhaltepunkt braucht der Umlauf {_bus(one.value)} (beides bewiesen)."
    return "info", (f"Ein Ladeplatz je Endhaltepunkt kostet {_bus(gap)} mehr: {_bus(one.value)} statt {_bus(many.value)} bei unbegrenzten Plätzen "
                    f"(beides bewiesen, die Ladeleistung ist dieselbe).")
