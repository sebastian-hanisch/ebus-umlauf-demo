"""Energiemodell und unabhängiger Prüfer.

Ein Bus startet voll (Ladestand = C), fährt eine Kette von Fahrten, darf zwischen zwei Fahrten eine Leerfahrt zwischen den Endhaltepunkten machen und dort,
wo ein Lader steht, laden. Der Ladestand darf nie unter die Reserve (10 % von C) fallen. Laden ist linear (Ladeleistung P bis höchstens C, keine Ladekurve);
nutzbar ist die Wartezeit abzüglich Leerfahrt, Mindest-Wendezeit und An-/Abstecken. Ein Ladevorgang belegt einen Ladeplatz während der GANZEN Wartezeit
am Haltepunkt (Annahme: überschätzt die Belegung gegenüber kurzen realen Ladevorgängen).

Der Prüfer `check_plan` rechnet in Fließkomma und ohne die Rundung des Lösers (0,01 kWh) nach: jede Lösung der App, ob Regel oder CP-SAT, wird von ihm angenommen
oder abgelehnt."""

from dataclasses import dataclass, field

import ebu_constants as C

EPS = 1e-9


@dataclass(frozen=True)
class Params:
    c: float                 # Batteriekapazität (kWh)
    p: float                 # Ladeleistung am Endhaltepunkt (kW), 0 = kein Laden
    fw: float = 1.0          # Verbrauchsfaktor (1,0 Sommer, 1,36 Winter)
    chargers: str = "beide"  # "beide" oder "nur A"
    slots: int = C.SLOTS_UNLIMITED   # Ladeplätze je Endhaltepunkt

    @property
    def reserve(self) -> float:
        return C.RESERVE_FRACTION * self.c

    def charger_at(self, site: int) -> bool:
        return self.chargers == "beide" or site == 0


@dataclass(frozen=True)
class Plan:
    chains: tuple                          # je Bus eine Kette von Fahrtnummern
    charged: frozenset = frozenset()       # Anschlüsse (i, j), auf denen geladen wird
    diesel: frozenset = field(default_factory=frozenset)   # Nummern der Ketten (Index in chains), die Dieselbusse sind

    @property
    def buses(self) -> int:
        return len(self.chains)

    @property
    def diesel_buses(self) -> int:
        return len(self.diesel)


def trip_energy(inst, prm: Params) -> list:
    return [d * C.KWH_PER_KM * prm.fw for d in inst.dist]


def deadhead_energy(dh_km: float, prm: Params) -> float:
    return dh_km * C.KWH_PER_KM * prm.fw


def charge_site(inst, prm: Params, i: int, j: int):
    """Haltepunkt, an dem auf dem Anschluss i -> j geladen würde: am Ankunftshaltepunkt der Fahrt i, sonst am Starthaltepunkt der Fahrt j (nach der
    Leerfahrt), sonst None. Ohne Ladeleistung nie."""
    if prm.p <= 0:
        return None
    u, v = inst.dest[i], inst.orig[j]
    if prm.charger_at(u):
        return u
    if prm.charger_at(v):
        return v
    return None


def charge_minutes(slack: int) -> int:
    """Nutzbare Ladezeit: Wartezeit minus Leerfahrt und Wendezeit (schon im Spielraum `slack`) minus An-/Abstecken."""
    return max(0, slack - C.CHARGE_OVERHEAD_MIN)


def charge_gain(prm: Params, slack: int) -> float:
    return prm.p * charge_minutes(slack) / 60.0


def dh_minutes(inst, i: int, j: int) -> int:
    return 0 if inst.dest[i] == inst.orig[j] else inst.dh_min


def charge_interval(inst, i: int, j: int, site: int):
    """Zeitraum (Beginn, Ende) der Platzbelegung in Minuten: die ganze Wartezeit am Haltepunkt."""
    dht = dh_minutes(inst, i, j)
    if site == inst.dest[i]:
        return inst.end[i], inst.start[j] - dht
    return inst.end[i] + dht, inst.start[j]


def full_charging(inst, prm: Params, chains) -> frozenset:
    """Alle Anschlüsse der Ketten, auf denen geladen werden kann (ohne Platzgrenze)."""
    tab = arc_table(inst)
    out = set()
    for ch in chains:
        for a, b in zip(ch, ch[1:]):
            slack = tab[(a, b)][1]
            if charge_site(inst, prm, a, b) is not None and charge_minutes(slack) > 0:
                out.add((a, b))
    return frozenset(out)


def arc_table(inst) -> dict:
    return {(i, j): (dh, slack) for i, j, dh, slack in inst.arcs}


def peak_slots_used(inst, prm: Params, charged) -> dict:
    """Höchste gleichzeitige Platzbelegung je Haltepunkt für die Menge der Ladeanschlüsse."""
    occ = {}
    for (a, b) in charged:
        site = charge_site(inst, prm, a, b)
        bg, en = charge_interval(inst, a, b, site)
        occ.setdefault(site, []).append((bg, max(bg + 1, en)))
    peaks = {}
    for site, iv in occ.items():
        ev = sorted([(b, 1) for b, _ in iv] + [(en, -1) for _, en in iv], key=lambda z: (z[0], z[1]))
        cur = mx = 0
        for _, d in ev:
            cur += d
            mx = max(mx, cur)
        peaks[site] = mx
    return peaks


def simulate_chain(inst, prm: Params, tab: dict, chain, charged) -> bool:
    """Prüft eine Fahrtenfolge in Fließkomma: Anschlüsse zulässig, Ladestand nie unter der Reserve, Laden nur auf den Anschlüssen in `charged`."""
    e = trip_energy(inst, prm)
    soc = prm.c
    if e[chain[0]] + prm.reserve > soc + EPS:
        return False
    soc -= e[chain[0]]
    for a, b in zip(chain, chain[1:]):
        t = tab.get((a, b))
        if t is None:
            return False
        dh_km, slack = t
        soc -= deadhead_energy(dh_km, prm)
        if soc < prm.reserve - EPS:
            return False
        if (a, b) in charged:
            if charge_site(inst, prm, a, b) is None:
                return False
            soc = min(prm.c, soc + charge_gain(prm, slack))
        if soc - e[b] < prm.reserve - EPS:
            return False
        soc -= e[b]
    return True


def check_plan(inst, prm: Params, plan: Plan):
    """Unabhängiger Prüfer. Rückgabe (ok, Begründung). Diesel-Ketten brauchen nur zulässige Anschlüsse, Elektro-Ketten zusätzlich Energie."""
    seen = sorted(x for ch in plan.chains for x in ch)
    if seen != list(range(inst.n)):
        return False, "die Ketten sind keine Partition der Fahrten"
    tab = arc_table(inst)
    for k, ch in enumerate(plan.chains):
        if k in plan.diesel:
            if any((a, b) not in tab for a, b in zip(ch, ch[1:])):
                return False, f"Diesel-Kette {k}: unzulässiger Anschluss"
        elif not simulate_chain(inst, prm, tab, ch, plan.charged):
            return False, f"Kette {k}: der Ladestand fällt unter die Reserve oder ein Anschluss ist unzulässig"
    on_diesel = {(a, b) for k in plan.diesel for a, b in zip(plan.chains[k], plan.chains[k][1:])}
    if plan.charged & on_diesel:
        return False, "geladen auf einem Anschluss eines Dieselbusses"
    in_chains = {(a, b) for ch in plan.chains for a, b in zip(ch, ch[1:])}
    if not plan.charged <= in_chains:
        return False, "Ladeanschluss ohne Anschluss in einer Kette"
    if prm.slots < inst.n:
        for site, peak in peak_slots_used(inst, prm, plan.charged).items():
            if peak > prm.slots:
                return False, f"am Haltepunkt {'AB'[site]} laden gleichzeitig {peak} Busse (Plätze: {prm.slots})"
    return True, "zulässig"


def soc_profile(inst, prm: Params, chain, charged) -> list:
    """Ladestand je Fahrt einer Kette: [(Ladestand bei Abfahrt nach dem Laden, Ladestand bei Ankunft)]; für die Darstellung (der Prüfer rechnet unabhängig)."""
    e = trip_energy(inst, prm)
    tab = arc_table(inst)
    soc = prm.c
    out = []
    for k, t in enumerate(chain):
        if k > 0:
            dh_km, slack = tab[(chain[k - 1], t)]
            soc -= deadhead_energy(dh_km, prm)
            if (chain[k - 1], t) in charged:
                soc = min(prm.c, soc + charge_gain(prm, slack))
        out.append((soc, soc - e[t]))
        soc -= e[t]
    return out


def chain_energy(inst, prm: Params, chain) -> float:
    """Gesamtenergie einer Kette ohne Laden: Fahrten plus Leerfahrten (kWh)."""
    tab = arc_table(inst)
    e = trip_energy(inst, prm)
    return sum(e[t] for t in chain) + sum(deadhead_energy(tab[(a, b)][0], prm) for a, b in zip(chain, chain[1:]))
