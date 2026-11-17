"""Abgeleitete Zahlen der Messreihen (Quelle der README-Zahlen) und der Messbericht tools/MESSBERICHT.md.

Wird von tools/messreihe_auswertung.py am Ende aufgerufen: `fakten(...)` liefert ein Wörterbuch (steht in data/messreihe.json unter „fakten“), `bericht(...)` schreibt
den Text. Jede Zahl der README steht hier oder in der Auswertung; tests/test_claims.py prüft die README-Zahlen gegen dieses Wörterbuch."""

import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ebu_constants as C  # noqa: E402
import ebu_diesel as D  # noqa: E402
import ebu_energy as E  # noqa: E402
import ebu_scenario as S  # noqa: E402


def _paired(rows, dim_key, a_val, b_val, group_keys):
    """Paare gleicher Gruppe mit Wert a gegen Wert b in `dim_key`; nur beiderseits bewiesene Zeilen. Rückgabe Zählung (b schlechter / gleich / besser als a)."""
    idx = defaultdict(dict)
    for r in rows:
        idx[tuple(r[k] for k in group_keys)][r[dim_key]] = r
    worse = same = better = 0
    sa = sb = 0.0
    for g in idx.values():
        ra, rb = g.get(a_val), g.get(b_val)
        if ra is None or rb is None or not (ra["proven"] and rb["proven"]):
            continue
        sa += ra["ub"] - ra["diesel"]
        sb += rb["ub"] - rb["diesel"]
        if rb["ub"] > ra["ub"]:
            worse += 1
        elif rb["ub"] == ra["ub"]:
            same += 1
        else:
            better += 1
    n = worse + same + better
    return dict(pairs=n, worse=worse, same=same, better=better, mean_a=sa / n if n else None, mean_b=sb / n if n else None)


def fakten(rampe, plaetze, takt, gemischt) -> dict:
    out = {}
    # Lader nur A gegen beide (Rampe, beiderseits bewiesen)
    out["lader"] = _paired([r for r in rampe if r["p"] > 0], "chargers", "beide", "nur A", ("seed", "season", "c", "p"))     # ohne Laden (P = 0) sind die Aufgaben identisch
    out["lader_ohne_laden"] = _paired([r for r in rampe if r["p"] == 0], "chargers", "beide", "nur A", ("seed", "season", "c", "p"))["pairs"]
    # Ladeplätze: ein Platz und zwei Plätze gegen unbegrenzt, je Seed und Zelle
    out["plaetze_1"] = _paired(plaetze, "slots", C.SLOTS_UNLIMITED, 1, ("seed", "season", "c", "p", "chargers"))
    out["plaetze_2"] = _paired(plaetze, "slots", C.SLOTS_UNLIMITED, 2, ("seed", "season", "c", "p", "chargers"))
    # Ladeplätze nach Ladeleistung (ein Platz gegen unbegrenzt)
    by_p = {}
    for p in sorted({r["p"] for r in plaetze}):
        sub = [r for r in plaetze if r["p"] == p]
        by_p[str(p)] = _paired(sub, "slots", C.SLOTS_UNLIMITED, 1, ("seed", "season", "c", "p", "chargers"))
    out["plaetze_1_nach_p"] = by_p
    out["plaetze_bewiesen"] = {str(sl): [sum(1 for r in plaetze if r["slots"] == sl and r["proven"]), sum(1 for r in plaetze if r["slots"] == sl)] for sl in (1, 2, C.SLOTS_UNLIMITED)}
    # Energie der energiereichsten Dieselkette gegen die nutzbare Batterie (nur P = 0)
    chain = {}
    for r in rampe:
        if r["p"] != 0 or r["chargers"] != "beide":
            continue
        key = (r["seed"], r["season"])
        if key not in chain:
            inst = S.generate(r["seed"])
            prm = E.Params(1.0, 0.0, 1.0 if r["season"] == "Sommer" else C.WINTER_FACTOR)
            chain[key] = max(E.chain_energy(inst, prm, ch) for ch in D.diesel_plan(inst).chains)
    suff = [r for r in rampe if r["p"] == 0 and r["chargers"] == "beide" and 0.9 * r["c"] >= chain[(r["seed"], r["season"])] - 1e-9]
    insuff = [r for r in rampe if r["p"] == 0 and r["chargers"] == "beide" and 0.9 * r["c"] < chain[(r["seed"], r["season"])] - 1e-9]
    out["kettenenergie"] = dict(
        p0_rows=len(suff) + len(insuff), sufficient=len(suff), sufficient_zero=sum(1 for r in suff if r["ub"] == r["diesel"]),
        sufficient_proven_zero=sum(1 for r in suff if r["proven"] and r["ub"] == r["diesel"]),
        sufficient_kwh_min=min(chain[(r["seed"], r["season"])] for r in suff), sufficient_kwh_max=max(chain[(r["seed"], r["season"])] for r in suff),
        insufficient=len(insuff), insufficient_positive=sum(1 for r in insuff if r["ub"] is not None and r["ub"] > r["diesel"]),
        insufficient_positive_proven=sum(1 for r in insuff if r["lb"] > r["diesel"]),
        insufficient_zero_proven=sum(1 for r in insuff if r["proven"] and r["ub"] == r["diesel"]),
        chain_kwh_min=min(chain.values()), chain_kwh_max=max(chain.values()))
    # Verhältnis Mittel P = 0 → 10 → 20 (Sommer, beide, je Batterie)
    ramp = {}
    for c in C.RAMP_C:
        ramp[str(c)] = {}
        for p in C.RAMP_P:
            cell = [r for r in rampe if r["season"] == "Sommer" and r["chargers"] == "beide" and r["c"] == c and r["p"] == p]
            ramp[str(c)][str(p)] = statistics.mean(r["ub"] - r["diesel"] for r in cell if r["ub"] is not None)
    out["sommer_beide_mittel"] = ramp
    # Winter gegen Sommer: Mittel je Zelle (Batterie, Ladeleistung, Ladersetzung)
    larger = smaller = cells = 0
    for ch in C.CHARGER_OPTIONS:
        for c in C.RAMP_C:
            for p in C.RAMP_P:
                def mean_of(season):
                    sub = [r for r in rampe if r["season"] == season and r["chargers"] == ch and r["c"] == c and r["p"] == p and r["ub"] is not None]
                    return statistics.mean(r["ub"] - r["diesel"] for r in sub)
                s_, w_ = mean_of("Sommer"), mean_of("Winter")
                cells += 1
                larger += w_ > s_ + 1e-9
                smaller += w_ < s_ - 1e-9
    pl = pw = 0
    pc = 0
    for ch in C.CHARGER_OPTIONS:
        for c in C.RAMP_C:
            for p in C.RAMP_P:
                def cell_of(season):
                    return [r for r in rampe if r["season"] == season and r["chargers"] == ch and r["c"] == c and r["p"] == p]
                a_, b_ = cell_of("Sommer"), cell_of("Winter")
                if all(r["proven"] for r in a_ + b_):
                    pc += 1
                    ms, mw = statistics.mean(r["ub"] - r["diesel"] for r in a_), statistics.mean(r["ub"] - r["diesel"] for r in b_)
                    pl += mw > ms + 1e-9
                    pw += mw < ms - 1e-9
    out["winter"] = dict(cells=cells, larger=larger, smaller=smaller, fully_proven_cells=pc, fully_proven_larger=pl, fully_proven_smaller=pw)
    # Takt gegen Generator an denselben Zellen (Sommer/Winter, beide)
    cmp = {}
    for season in ("Sommer", "Winter"):
        for c in (60, 80, 100):
            for p in (0, 10, 20):
                a = [r for r in rampe if r["season"] == season and r["chargers"] == "beide" and r["c"] == c and r["p"] == p and r["ub"] is not None]
                b = [r for r in takt if r["season"] == season and r["c"] == c and r["p"] == p and r["ub"] is not None]
                cmp[f"{season}|{c}|{p}"] = dict(zufall=statistics.mean(r["ub"] - r["diesel"] for r in a), takt=statistics.mean(r["ub"] - r["diesel"] for r in b),
                                                takt_proven=sum(r["proven"] for r in b), takt_lb=statistics.mean(max(0, r["lb"] - r["diesel"]) for r in b), takt_diesel=statistics.mean(r["diesel"] for r in b), takt_n=statistics.mean(r["n"] for r in b),
                                                takt_layover=sorted({r["layover"] for r in b}))
    out["takt_gegen_zufall"] = cmp
    # Rechenzeit
    secs = [r["seconds"] for r in rampe + plaetze if "seconds" in r]
    proven = [r["seconds"] for r in rampe + plaetze if r["status"] == "OPTIMAL"]
    out["zeit"] = dict(rows=len(secs), median=statistics.median(secs), proven_rows=len(proven), proven_under_1s=sum(1 for s in proven if s <= 1.0), proven_under_5s=sum(1 for s in proven if s <= 5.0),
                       proven_median=statistics.median(proven), proven_max=max(proven))
    # Gemischte Flotte: Zeilen mit Dieselbusanteil
    gm_rows = [r for r in gemischt if r["diesel_buses"] is not None]
    gmx = gemischt
    out["gemischt"] = dict(rows=len(gemischt), proven=sum(r["status"] == "OPTIMAL" for r in gemischt), full_electric_rows=sum(1 for r in gm_rows if r["diesel_buses"] == 0),
                           reserve0_mean=statistics.mean(r["diesel_buses"] for r in gm_rows if r["reserve_buses"] == 0), reserve1_mean=statistics.mean(r["diesel_buses"] for r in gm_rows if r["reserve_buses"] == 1),
                           reserve0_proven=sum(1 for r in gmx if r["reserve_buses"] == 0 and r["status"] == "OPTIMAL"), reserve1_proven=sum(1 for r in gmx if r["reserve_buses"] == 1 and r["status"] == "OPTIMAL"),
                           reserve1_lb_mean=statistics.mean(r["bound"] for r in gmx if r["reserve_buses"] == 1 and r["bound"] is not None),
                           reserve_helps=sum(1 for k, g in _group(gm_rows, ("seed", "season", "c", "p")).items() if len(g) == 2 and g[1]["diesel_buses"] < g[0]["diesel_buses"]),
                           reserve_pairs=sum(1 for k, g in _group(gm_rows, ("seed", "season", "c", "p")).items() if len(g) == 2))
    return out


def _group(rows, keys):
    d = defaultdict(dict)
    for r in rows:
        d[tuple(r[k] for k in keys)][r["reserve_buses"]] = r
    return d


def bericht(data: dict, path: Path) -> None:
    f = data["fakten"]
    m = data["meta"]
    L = ["# Messbericht (erzeugt von tools/messreihe_auswertung.py; Rohdaten in tools/messdaten/)", "",
         "Alle Zahlen sind Messungen mit dem Code dieser Demo auf dem Entwicklungsrechner (CP-SAT, Zeitlimit "
         f"{m['time_limit']:.0f} s je Rechnung, höchstens 3 Arbeiter). Fahrpläne, Verbrauch, Ladeleistung und Winterfaktor sind Annahmen des Generators.", "",
         "## Umfang", "", "```", *[f"{k}: {v}" for k, v in m.items()], "```", "", "## Abgeleitete Zahlen", "", "```"]
    for k, v in f.items():
        L.append(f"{k}: {v}")
    L += ["```", "", "## Regeln", "", "```"]
    for k, v in data["regeln"].items():
        L.append(f"{k}: {v}")
    L += ["```", ""]
    for part in ("tag", "tag2"):
        if part in data:
            L += [f"## Grenze: ganzer Tag ({part})", "", "```", f"{part}: {data[part]}", "```", ""]
    path.write_text("\n".join(L), encoding="utf-8")
