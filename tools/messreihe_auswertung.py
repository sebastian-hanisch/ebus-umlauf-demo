"""Wertet die Rohdaten aus tools/messdaten/*.jsonl aus und schreibt data/messreihe.json (die App liest nur diese Datei) und tools/MESSBERICHT.md.

Monotone Hülle (dokumentiert, im Bericht benannt): Ein Umlauf, der mit weniger Batterie, weniger Ladeleistung, weniger Ladern, weniger Ladeplätzen oder
höherem Verbrauch zulässig ist, ist auch mit mehr zulässig. Darum gilt für die beste bekannte Zahl (obere Schranke) jeder Zelle das Minimum über alle
schwächeren Zellen desselben Fahrplans, und für die bewiesene untere Schranke das Maximum über alle stärkeren. Der Löser fand sonst in einzelnen Zellen
mit mehr Ressourcen nicht einmal die Lösung der ärmeren Zelle. „Bewiesen“ heißt danach: obere = untere Schranke.
Aufruf:  python tools/messreihe_auswertung.py"""

import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import ebu_constants as C  # noqa: E402

RAW = ROOT / "tools" / "messdaten"
OUT_JSON = ROOT / "data" / "messreihe.json"
OUT_MD = ROOT / "tools" / "MESSBERICHT.md"
FW = {"Sommer": 1.0, "Winter": C.WINTER_FACTOR}
RULES = ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen")
RULE_NAMES = {"spaet": "Spät", "frueh": "Früh", "soc_max": "Ladestand max.", "soc_min": "Ladestand min.", "diesel_trennen": "Dieselplan, dann trennen"}


def load(part: str) -> list:
    """Rohzeilen eines Teils: tools/messdaten/<teil>_<shard>.jsonl, ersatzweise die gepackte Fassung <teil>.jsonl.gz (die Reihe `regeln` hat 12.800 Zeilen)."""
    rows = []
    for f in sorted(RAW.glob(f"{part}_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    packed = RAW / f"{part}.jsonl.gz"
    if not rows and packed.exists():
        with gzip.open(packed, "rt", encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    return rows


def fmt(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def strength(r) -> tuple:
    """Größer = stärkere Ressourcen (Batterie, Ladeleistung, Lader, Plätze) bzw. kleinerer Verbrauch."""
    return (r["c"], r["p"], 1 if r["chargers"] == "beide" else 0, r["slots"], -FW[r["season"]])


def leq(a: tuple, b: tuple) -> bool:
    return all(x <= y for x, y in zip(a, b))


def hull(rows: list, key_ub: str = "value", key_lb: str = "bound") -> None:
    """Setzt r['ub'], r['lb'] (Busse bzw. Dieselbusse), r['proven'] nach der monotonen Hülle je (Fahrplan-Seed, Teil)."""
    by = defaultdict(list)
    for r in rows:
        by[(r["part"], r["timetable"], r["seed"])].append(r)
    for grp in by.values():
        for r in grp:
            ub = r[key_ub] if r[key_ub] is not None else 10 ** 6
            lb = r[key_lb] if r[key_lb] is not None else 0
            for o in grp:
                if o is r:
                    continue
                if leq(strength(o), strength(r)) and o[key_ub] is not None:
                    ub = min(ub, o[key_ub])
                if leq(strength(r), strength(o)) and o[key_lb] is not None:
                    lb = max(lb, o[key_lb])
            r["ub"], r["lb"] = (None if ub >= 10 ** 6 else ub), lb
            r["proven"] = r["ub"] is not None and r["ub"] == r["lb"]


def cell_stats(rows: list) -> dict:
    n = len(rows)
    ub = [r["ub"] - r["diesel"] for r in rows if r["ub"] is not None]
    lb = [max(0, r["lb"] - r["diesel"]) for r in rows]
    return dict(n=n, ub_mean=statistics.mean(ub) if ub else None, lb_mean=statistics.mean(lb), proven=sum(r["proven"] for r in rows),
                positive=sum(1 for r in rows if r["ub"] is not None and r["ub"] > r["diesel"]), diesel_mean=statistics.mean(r["diesel"] for r in rows),
                no_solution=sum(1 for r in rows if r["ub"] is None))


def group(rows, keyf):
    d = defaultdict(list)
    for r in rows:
        d[keyf(r)].append(r)
    return d


def ramp_table(rows) -> dict:
    out = {}
    for (season, chargers), g in group(rows, lambda r: (r["season"], r["chargers"])).items():
        out[f"{season}|{chargers}"] = {f"{c}|{p}": cell_stats(gg) for (c, p), gg in group(g, lambda r: (r["c"], r["p"])).items()}
    return out


def pair_violations(rows, dim: str, rulekey) -> list:
    """[Verletzungen, Paare]: benachbarte Zellen derselben Seed/Jahreszeit/Lader (Batterie bzw. Leistung aufsteigend); Verletzung = mehr Busse trotz mehr Ressource."""
    other = "p" if dim == "c" else "c"
    grid = C.RAMP_C if dim == "c" else C.RAMP_P
    idx = {(r["seed"], r["season"], r["chargers"], r["c"], r["p"]): r for r in rows}
    bad = tot = 0
    for r in rows:
        i = grid.index(r[dim])
        if i + 1 >= len(grid):
            continue
        nxt = idx.get((r["seed"], r["season"], r["chargers"], grid[i + 1] if dim == "c" else r["c"], grid[i + 1] if dim == "p" else r["p"]))
        if nxt is None:
            continue
        a, b = rulekey(r), rulekey(nxt)
        if a is None or b is None:
            continue
        tot += 1
        bad += b > a
    return [bad, tot]


def pair_example(rows, dim: str, rulekey, optima=None):
    """Das Paar benachbarter Zellen mit der größten Verschlechterung trotz mehr Ressource (kleinster Seed bei Gleichstand), oder None.
    Mit `optima` ({(seed, season, chargers, c, p): bewiesenes Optimum}) nur Paare, deren beide Optima bewiesen sind; die Optima kommen in das Ergebnis."""
    grid = C.RAMP_C if dim == "c" else C.RAMP_P
    idx = {(r["seed"], r["season"], r["chargers"], r["c"], r["p"]): r for r in rows}
    best = None
    for r in rows:
        i = grid.index(r[dim])
        if i + 1 >= len(grid):
            continue
        nxt = idx.get((r["seed"], r["season"], r["chargers"], grid[i + 1] if dim == "c" else r["c"], grid[i + 1] if dim == "p" else r["p"]))
        if nxt is None or rulekey(r) is None or rulekey(nxt) is None:
            continue
        worse = rulekey(nxt) - rulekey(r)
        cand = (worse, -r["seed"], r["season"], r["chargers"])
        ex = dict(seed=r["seed"], season=r["season"], chargers=r["chargers"], c_from=r["c"], p_from=r["p"], c_to=nxt["c"], p_to=nxt["p"], buses_from=rulekey(r), buses_to=rulekey(nxt))
        if optima is not None:
            o1 = optima.get((r["seed"], r["season"], r["chargers"], r["c"], r["p"]))
            o2 = optima.get((r["seed"], r["season"], r["chargers"], nxt["c"], nxt["p"]))
            if o1 is None or o2 is None:
                continue
            ex.update(opt_from=o1, opt_to=o2)
        if worse > 0 and (best is None or cand > best[0]):
            best = (cand, ex)
    return None if best is None else best[1]


def build_data() -> dict:
    """Wertet alle Rohdaten aus (rein, ohne Dateien zu schreiben); tests/test_messreihe.py vergleicht das Ergebnis mit data/messreihe.json."""
    rampe = load("rampe")
    plaetze = load("plaetze")
    gemischt = load("gemischt")
    takt = load("takt")
    if not rampe:
        raise SystemExit("keine Rohdaten")
    for part_rows in (rampe, plaetze, takt):
        if part_rows:
            hull(part_rows)

    data = {"meta": {}, "rampe": ramp_table(rampe), "takt": ramp_table(takt)}
    # Ladeplätze
    pl = {}
    for (season, c, p, ch), g in group(plaetze, lambda r: (r["season"], r["c"], r["p"], r["chargers"])).items():
        pl[f"{season}|{c}|{p}|{ch}"] = {str(sl): cell_stats(gg) for sl, gg in group(g, lambda r: r["slots"]).items()}
    data["plaetze"] = dict(sorted(pl.items()))
    # Gemischte Flotte: keine Hülle über die Reserve (andere Aufgabe je Reserve); Rohwerte
    gm = {}
    for (season, c, p, rb), g in group(gemischt, lambda r: (r["season"], r["c"], r["p"], r["reserve_buses"])).items():
        vals = [r["diesel_buses"] for r in g if r["diesel_buses"] is not None]
        gm[f"{season}|{c}|{p}|{rb}"] = dict(n=len(g), mean=statistics.mean(vals) if vals else None, proven=sum(r["status"] == "OPTIMAL" for r in g),
                                           fleet_mean=statistics.mean(r["budget"] for r in g))
    data["gemischt"] = dict(sorted(gm.items(), key=lambda kv: (kv[0].split("|")[0] != "Sommer", int(kv[0].split("|")[3]), int(kv[0].split("|")[1]), int(kv[0].split("|")[2]))))

    # Regeln
    pos_proven = [r for r in rampe if r["proven"] and r["ub"] > r["diesel"]]
    pos_all = [r for r in rampe if r["ub"] is not None and r["ub"] > r["diesel"]]
    per_rule = {}
    for name in RULES:
        extra = [r["rules"][name] - r["ub"] for r in pos_proven if r["rules"].get(name) is not None]
        extra_all = [r["rules"][name] - r["ub"] for r in pos_all if r["rules"].get(name) is not None]
        per_rule[name] = dict(
            mean_extra=statistics.mean(extra), median_extra=statistics.median(extra), hits=sum(1 for x in extra if x == 0), of=len(extra),
            no_solution=sum(1 for r in pos_proven if r["rules"].get(name) is None), mean_extra_all=statistics.mean(extra_all), hits_all=sum(1 for x in extra_all if x == 0), of_all=len(extra_all))
    best_extra = [min(v for k, v in r["rules"].items() if k in RULES and v is not None) - r["ub"] for r in pos_proven]
    best_extra_all = [min(v for k, v in r["rules"].items() if k in RULES and v is not None) - r["ub"] for r in pos_all]
    nm = {}
    for key in ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen", "soc_max_frueh", "soc_max_spaet"):
        rk = (lambda k: (lambda r: r["rules"].get(k)))(key)
        nm[key] = dict(c=pair_violations(rampe, "c", rk), p=pair_violations(rampe, "p", rk))
    raw_ok = [r for r in rampe if r["status"] == "OPTIMAL"]
    opt_key = lambda r: r["value"]
    mono = dict(c=pair_violations(raw_ok, "c", opt_key), p=pair_violations(raw_ok, "p", opt_key))
    for key, d in per_rule.items():
        d["kurz"] = (f"Mittel +{fmt(d['mean_extra'])} Busse, Median +{fmt(d['median_extra'], 0)}, trifft in {d['hits']} von {d['of']}")
    data["regeln"] = dict(per_rule=per_rule, positive_proven=len(pos_proven), positive_all=len(pos_all), best_of=dict(mean_extra=statistics.mean(best_extra),
                          median_extra=statistics.median(best_extra), hits=sum(1 for x in best_extra if x == 0), of=len(best_extra), max_extra=max(best_extra),
                          mean_extra_all=statistics.mean(best_extra_all), hits_all=sum(1 for x in best_extra_all if x == 0), of_all=len(best_extra_all)),
                          nonmono=nm, opt_monotone=mono)

    # Große Reihe nur mit Regeln (200 Zufalls-Seeds, kein Löser)
    gross = load("regeln")
    if gross:
        gnm = {}
        for key in ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen", "soc_max_frueh", "soc_max_spaet"):
            rk = (lambda k: (lambda r: r["rules"].get(k)))(key)
            gnm[key] = dict(c=pair_violations(gross, "c", rk), p=pair_violations(gross, "p", rk))
        base = [r for r in gross if all(r["rules"].get(k) is not None for k in ("soc_max", "soc_max_frueh", "soc_max_spaet"))]
        differ = sum(1 for r in base if len({r["rules"]["soc_max"], r["rules"]["soc_max_frueh"], r["rules"]["soc_max_spaet"]}) > 1)
        pair_diff = {f"{a}|{b}": sum(1 for r in gross if r["rules"].get(a) is not None and r["rules"].get(b) is not None and r["rules"][a] != r["rules"][b])
                     for a, b in (("spaet", "frueh"), ("spaet", "soc_max"), ("spaet", "soc_min"), ("frueh", "soc_max"), ("frueh", "soc_min"), ("soc_max", "soc_min"),
                                  ("soc_max", "diesel_trennen"), ("soc_max", "soc_max_frueh"), ("soc_max", "soc_max_spaet"), ("soc_max_frueh", "soc_max_spaet"))}
        examples = {f"{k}|{dim}": pair_example(gross, dim, (lambda kk: (lambda r: r["rules"].get(kk)))(k)) for k in ("spaet", "frueh", "soc_max", "soc_min") for dim in ("c", "p")}
        optima = {(r["seed"], r["season"], r["chargers"], r["c"], r["p"]): r["ub"] for r in rampe if r["proven"]}
        sweep_rows = [r for r in gross if r["seed"] in C.SWEEP_SEEDS]
        examples_in_sweep = {f"{k}|{dim}": pair_example(sweep_rows, dim, (lambda kk: (lambda r: r["rules"].get(kk)))(k), optima) for k in ("spaet", "frueh", "soc_max", "soc_min") for dim in ("c", "p")}
        data["regeln"]["grosse_reihe"] = dict(examples=examples, examples_in_sweep=examples_in_sweep, rows=len(gross), seeds=len({r["seed"] for r in gross}), nonmono=gnm, tie_rows=len(base), tie_differ=differ, pair_differ=pair_diff,
                                              rejected=sum(1 for r in gross if r.get("rules_ok") is False), no_solution=sum(1 for r in gross if any(r["rules"].get(k) is None for k in RULES)),
                                              tie_better=dict(frueh=sum(1 for r in base if r["rules"]["soc_max_frueh"] < r["rules"]["soc_max"]), frueh_worse=sum(1 for r in base if r["rules"]["soc_max_frueh"] > r["rules"]["soc_max"]),
                                                              spaet=sum(1 for r in base if r["rules"]["soc_max_spaet"] < r["rules"]["soc_max"]), spaet_worse=sum(1 for r in base if r["rules"]["soc_max_spaet"] > r["rules"]["soc_max"])))

    # Meta
    def part_meta(rows):
        if not rows:
            return dict(rows=0)
        secs = [r["seconds"] for r in rows if "seconds" in r]
        return dict(rows=len(rows), proven_raw=sum(1 for r in rows if r["status"] == "OPTIMAL"), proven_hull=sum(1 for r in rows if r.get("proven")),
                    median_seconds=statistics.median(secs) if secs else None, max_seconds=max(secs) if secs else None,
                    under_1s=sum(1 for s in secs if s <= 1.0), under_5s=sum(1 for s in secs if s <= 5.0),
                    positive=sum(1 for r in rows if r.get("ub") is not None and r["ub"] > r["diesel"]),
                    positive_proven=sum(1 for r in rows if r.get("proven") and r["ub"] > r["diesel"]),
                    rejected=sum(1 for r in rows if r.get("check") is False or r.get("rules_ok") is False), n_min=min(r["n"] for r in rows), n_max=max(r["n"] for r in rows),
                    diesel_min=min(r["diesel"] for r in rows), diesel_max=max(r["diesel"] for r in rows), diesel_mean=statistics.mean(r["diesel"] for r in rows),
                    hull_improved=sum(1 for r in rows if r.get("ub") is not None and r.get("value") is not None and r["ub"] < r["value"]))

    data["meta"] = dict(seeds=list(C.SWEEP_SEEDS), time_limit=C.MESS_TIME_LIMIT_S, rampe=part_meta(rampe), plaetze=part_meta(plaetze), takt=part_meta(takt),
                        gemischt=dict(rows=len(gemischt), proven_raw=sum(1 for r in gemischt if r["status"] == "OPTIMAL"),
                                      rejected=sum(1 for r in gemischt if r.get("check") is False)))
    for part in ("tag", "tag2"):
        tag = load(part)
        if not tag:
            continue
        hull(tag)
        pos = [r for r in tag if r["ub"] is not None and r["ub"] > r["diesel"]]
        data[part] = dict(rows=len(tag), n_min=min(r["n"] for r in tag), n_max=max(r["n"] for r in tag), diesel_min=min(r["diesel"] for r in tag), diesel_max=max(r["diesel"] for r in tag),
                          positive=len(pos), positive_proven=sum(1 for r in pos if r["proven"]), proven=sum(1 for r in tag if r["proven"]), proven_raw=sum(1 for r in tag if r["status"] == "OPTIMAL"),
                          gap_mean=statistics.mean((r["ub"] - r["lb"]) for r in pos) if pos else None, gap_max=max((r["ub"] - r["lb"]) for r in tag if r["ub"] is not None),
                          no_solution=sum(1 for r in tag if r["ub"] is None), time_limit=C.MESS_TIME_LIMIT_S)
    import messbericht  # noqa: E402
    data["fakten"] = messbericht.fakten(rampe, plaetze, takt, gemischt)
    return data


def main():
    data = build_data()
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("geschrieben:", OUT_JSON, "Zeilen:", {k: v["rows"] for k, v in data["meta"].items() if isinstance(v, dict) and "rows" in v})
    write_report(data)


def write_report(d: dict) -> None:
    import messbericht
    messbericht.bericht(d, OUT_MD)
    print("geschrieben:", OUT_MD)


if __name__ == "__main__":
    main()
