"""Dieselumlauf: Mindestzahl von Bussen ohne Batteriegrenze = n − maximales Matching (minimale Wegeüberdeckung), mit Beweis nach König.

`max_matching` ist WÖRTLICH aus `fahrzeugflotte-demo/fz_dispatch.py` kopiert (dieselbe Dieselbasis: Mindestflotte = n − Matching); `tests/test_copies.py` bewacht
die Kopie (Quelltext-Vergleich, wenn der Nachbarordner vorhanden ist, und feste Referenzwerte). Nicht ändern: eine Korrektur gehört in die Quelle und
von dort in alle Kopien. Neu hier ist nur der Fahrtengraph (Leerfahrt, Wendezeit) und die Ladegrenze in den anderen Modulen."""

from dataclasses import dataclass


# ---------------------------------------------------------------------------------------------------
# Kopie aus fahrzeugflotte-demo (fz_dispatch.py), unverändert
# ---------------------------------------------------------------------------------------------------
def max_matching(n, adj):
    """Maximales Matching im zweigeteilten Graphen (links: Vorgänger, rechts: Nachfolger). Iterativ (erweiternde Wege mit eigenem Stapel), damit auch lange
    Ketten keine Rekursionsgrenze treffen. Rückgabe: (Größe, match_right) mit match_right[v] = u, wenn Kante u -> v im Matching, sonst -1."""
    match_right = [-1] * n
    size = 0
    for root in range(n):
        seen = set()
        stack = [(root, iter(adj[root]))]
        path = []                                   # (u, v): u wird auf v abgebildet, wenn der Weg gelingt
        found = False
        while stack and not found:
            u, it = stack[-1]
            advanced = False
            for v in it:
                if v in seen:
                    continue
                seen.add(v)
                path.append((u, v))
                if match_right[v] < 0:
                    found = True
                else:
                    stack.append((match_right[v], iter(adj[match_right[v]])))
                advanced = True
                break
            if found:
                break
            if not advanced:
                stack.pop()
                if path:
                    path.pop()
        if found:
            for u, v in path:
                match_right[v] = u
            size += 1
    return size, match_right


# ---------------------------------------------------------------------------------------------------
# Dieselumlauf dieser Demo
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DieselPlan:
    buses: int              # Mindestzahl Busse ohne Batteriegrenze = n − Matching
    chains: tuple           # eine Kette (Tupel von Fahrtnummern) je Bus
    matching_size: int
    cover_left: frozenset   # Knotenüberdeckung (König): linke Knoten ...
    cover_right: frozenset  # ... und rechte Knoten; |Überdeckung| = Größe des Matchings

    @property
    def cover_size(self):
        return len(self.cover_left) + len(self.cover_right)


def adjacency(inst):
    adj = [[] for _ in range(inst.n)]
    for i, j, _dh, _slack in inst.arcs:
        adj[i].append(j)
    return adj


def chains_from_next(n, nxt):
    """Ketten aus einer Nachfolger-Abbildung {i: j}, aufsteigend nach der ersten Fahrt."""
    has_pred = set(nxt.values())
    chains = []
    for i in range(n):
        if i not in has_pred:
            ch = [i]
            while ch[-1] in nxt:
                ch.append(nxt[ch[-1]])
            chains.append(tuple(ch))
    return chains


def diesel_plan(inst) -> DieselPlan:
    """Mindestumlauf ohne Batteriegrenze mit Beweis (Knotenüberdeckung gleicher Größe wie das Matching)."""
    n = inst.n
    adj = adjacency(inst)
    size, match_right = max_matching(n, adj)
    match_left = {u: v for v, u in enumerate(match_right) if u >= 0}
    # Alternierende Wege ab den ungematchten linken Knoten: links -> rechts über beliebige Kanten, rechts -> links über Matching-Kanten
    reach_left = {u for u in range(n) if u not in match_left}
    reach_right = set()
    stack = list(reach_left)
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in reach_right:
                reach_right.add(v)
                w = match_right[v]
                if w >= 0 and w not in reach_left:
                    reach_left.add(w)
                    stack.append(w)
    cover_left = frozenset(u for u in range(n) if u not in reach_left)
    cover_right = frozenset(reach_right)
    chains = tuple(chains_from_next(n, match_left))
    return DieselPlan(n - size, chains, size, cover_left, cover_right)


def verify_diesel_proof(inst, plan: DieselPlan):
    """Prüft den Beweis ohne Löser: (1) die Ketten sind eine Partition aller Fahrten mit zulässigen Anschlüssen, (2) jede Kante des Fahrtengraphen hat einen
    Endpunkt in der Überdeckung, (3) |Überdeckung| = n − Kettenzahl. Dann hat jede Überdeckung der Fahrten mindestens so viele Ketten. (ok, Begründung)."""
    n = inst.n
    if sorted(x for ch in plan.chains for x in ch) != list(range(n)):
        return False, "die Ketten sind keine Partition der Fahrten"
    arcs = {(i, j) for i, j, _d, _s in inst.arcs}
    for ch in plan.chains:
        if any((a, b) not in arcs for a, b in zip(ch, ch[1:])):
            return False, "eine Kette enthält einen unzulässigen Anschluss"
    if len(plan.chains) != plan.buses:
        return False, "Buszahl passt nicht zur Kettenzahl"
    for i, j in arcs:
        if i not in plan.cover_left and j not in plan.cover_right:
            return False, f"die Kante {i} -> {j} ist nicht überdeckt"
    if plan.cover_size != n - plan.buses:
        return False, "die Überdeckung ist nicht so groß wie das Matching"
    return True, "bewiesen: kein Umlauf ohne Batteriegrenze kommt mit weniger Bussen aus"
