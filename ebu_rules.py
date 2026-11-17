"""Einfache Regeln für den Elektro-Umlauf (Vergleichsverfahren gegen das bewiesene Optimum).

Die Fahrten werden in Abfahrtsreihenfolge verteilt. Für jede Fahrt wird unter den Bussen gewählt, die sie noch fahren können (Anschluss zulässig, Ladestand
reicht, auch nach der Fahrt noch über der Reserve); gibt es keinen, kommt ein neuer, voller Bus. Die Regeln unterscheiden sich nur in der Wahl:
  spaet      der Bus mit der kürzesten Standzeit (spätestens angekommen)
  frueh      der Bus mit der längsten Standzeit
  soc_max    der Bus mit dem höchsten Ladestand bei Abfahrt (nach dem Laden); Gleichstand: `tie`
  soc_min    der Bus mit dem niedrigsten Ladestand
und eine naheliegende Heuristik (ohne Quelle für den Praxiseinsatz):
  diesel_trennen   Dieselumlauf (Matching) elektrifizieren und die Kette dort trennen, wo die Batterie nicht reicht.
Laden: wo ein Lader steht und eine Ladezeit übrig ist, wird geladen, wenn ein Ladeplatz frei ist (Platzgrenze), sonst nicht.
Gleichstand beim Ladestand (z. B. alle Busse voll): `tie` = "liste" (Reihenfolge, in der die Busse eingesetzt wurden), "frueh" oder "spaet" (Standzeit)."""

import ebu_constants as C
from ebu_diesel import diesel_plan
from ebu_energy import (EPS, Params, Plan, arc_table, charge_gain, charge_interval, charge_minutes, charge_site, deadhead_energy, trip_energy)

RULES = ("spaet", "frueh", "soc_max", "soc_min")
RULE_LABELS = {
    "spaet": "Spät",
    "frueh": "Früh",
    "soc_max": "Ladestand max.",
    "soc_min": "Ladestand min.",
    "diesel_trennen": "Dieselplan, dann trennen",
}
TIES = ("liste", "frueh", "spaet")
TIE_LABELS = {"liste": "Einsatzreihenfolge", "frueh": "früh (längste Standzeit)", "spaet": "spät (kürzeste Standzeit)"}


class SlotBook:
    """Belegte Ladeplätze je Haltepunkt (Intervalle); prüft, ob ein weiterer Vorgang noch Platz hat."""

    def __init__(self, slots: int, n: int):
        self.limited = slots < n
        self.slots = slots
        self.iv = {0: [], 1: []}

    def free(self, site: int, bg: int, en: int) -> bool:
        if not self.limited:
            return True
        bg, en = bg, max(bg + 1, en)
        pts = [bg] + [b for b, e in self.iv[site] if bg <= b < en]
        for t in pts:
            used = sum(1 for b, e in self.iv[site] if b <= t < e)
            if used + 1 > self.slots:
                return False
        return True

    def book(self, site: int, bg: int, en: int):
        self.iv[site].append((bg, max(bg + 1, en)))


def _options(inst, prm: Params, tab, e, book: SlotBook, last: int, soc_end: float, j: int):
    """Ladestand bei Abfahrt der Fahrt j, wenn der Bus nach Fahrt `last` mit `soc_end` sie fährt; None, wenn nicht möglich. Rückgabe (s, geladen, site, interval)."""
    t = tab.get((last, j))
    if t is None:
        return None
    dh_km, slack = t
    s = soc_end - deadhead_energy(dh_km, prm)
    if s < prm.reserve - EPS:
        return None
    site = charge_site(inst, prm, last, j)
    charged, iv = False, None
    if site is not None and charge_minutes(slack) > 0:
        bg, en = charge_interval(inst, last, j, site)
        if book.free(site, bg, en):
            s = min(prm.c, s + charge_gain(prm, slack))
            charged, iv = True, (site, bg, en)
    if s - e[j] < prm.reserve - EPS:
        return None
    return s, charged, iv


def greedy(inst, prm: Params, rule: str, tie: str = "liste"):
    """Regel `rule` in Abfahrtsreihenfolge. Rückgabe Plan oder None, wenn eine Fahrt allein nicht fahrbar ist."""
    if rule not in RULES:
        raise ValueError(rule)
    tab = arc_table(inst)
    e = trip_energy(inst, prm)
    book = SlotBook(prm.slots, inst.n)
    buses = []   # [letzte Fahrt, Ladestand am Ende, Kette]
    charged = set()
    for j in range(inst.n):
        best = None
        for b, (last, soc_end, _ch) in enumerate(buses):
            o = _options(inst, prm, tab, e, book, last, soc_end, j)
            if o is None:
                continue
            s = o[0]
            if rule == "spaet":
                primary = (-inst.end[last],)
            elif rule == "frueh":
                primary = (inst.end[last],)
            else:
                level = -round(s, 6) if rule == "soc_max" else round(s, 6)
                if tie == "frueh":
                    primary = (level, inst.end[last])
                elif tie == "spaet":
                    primary = (level, -inst.end[last])
                else:
                    primary = (level,)
            key = (primary, b)
            if best is None or key < best[0]:
                best = (key, b, o)
        if best is None:
            if e[j] + prm.reserve > prm.c + EPS:
                return None
            buses.append([j, prm.c - e[j], [j]])
        else:
            _key, b, (s, did, iv) = best
            if did:
                charged.add((buses[b][0], j))
                book.book(*iv)
            buses[b][0] = j
            buses[b][1] = s - e[j]
            buses[b][2].append(j)
    return Plan(tuple(tuple(b[2]) for b in buses), frozenset(charged))


def diesel_trennen(inst, prm: Params):
    """Dieselumlauf des Matchings; wo der Ladestand nicht reicht, beginnt ein neuer voller Bus."""
    tab = arc_table(inst)
    e = trip_energy(inst, prm)
    book = SlotBook(prm.slots, inst.n)
    out, charged = [], set()
    for chain in diesel_plan(inst).chains:
        if e[chain[0]] + prm.reserve > prm.c + EPS:
            return None
        cur = [chain[0]]
        soc = prm.c - e[chain[0]]
        for b in chain[1:]:
            o = _options(inst, prm, tab, e, book, cur[-1], soc, b)
            if o is not None:
                s, did, iv = o
                if did:
                    charged.add((cur[-1], b))
                    book.book(*iv)
                cur.append(b)
                soc = s - e[b]
            else:
                out.append(tuple(cur))
                cur = [b]
                soc = prm.c - e[b]
        out.append(tuple(cur))
    return Plan(tuple(out), frozenset(charged))


def run_rule(inst, prm: Params, rule: str, tie: str = "liste"):
    return diesel_trennen(inst, prm) if rule == "diesel_trennen" else greedy(inst, prm, rule, tie)


def all_rules(inst, prm: Params, tie: str = "liste") -> dict:
    """Plan je Regel ({Name: Plan oder None})."""
    return {r: run_rule(inst, prm, r, tie) for r in (*RULES, "diesel_trennen")}


def best_rule(plans: dict):
    """(Name, Plan) der Regel mit den wenigsten Bussen (Gleichstand: Reihenfolge von `RULES`), None ohne Plan."""
    cand = [(p.buses, k) for k, p in plans.items() if p is not None]
    if not cand:
        return None
    _n, name = min(cand, key=lambda z: (z[0], list(plans).index(z[1])))
    return name, plans[name]
