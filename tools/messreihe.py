"""Messreihen der Demo (Quelle aller Zahlen der README): schreibt Rohzeilen nach tools/messdaten/<teil>_<shard>.jsonl.

Teile:
  rampe    Aufschlag gegen den Dieselumlauf: Batterie x Ladeleistung x Lader x Jahreszeit, Zufalls-Seeds 0 bis 9, Ladeplätze unbegrenzt, plus die Regeln
  plaetze  Ladeplätze je Endhaltepunkt (1, 2, unbegrenzt) bei Ladeleistung 20/40/150 kW, zwei Batterie-/Jahreszeit-Stufen
  gemischt gemischte Flotte: Dieselbusse bei fester Flottengröße (Dieselmindestflotte + Reserve)
  takt     Preset „Gleichmäßiger Takt“: Rampe mit weniger Zellen
  tag2     Grenze: ganzer Tag mit halbem Takt (rund 190 Fahrten), 5 Seeds
  regeln   nur die Regeln (kein Löser) auf 200 Zufalls-Seeds im Raster der Rampe: Nicht-Monotonie und Gleichstandsbruch
  tag      Grenze: derselbe Generator über den ganzen Tag (rund 100 Fahrten, nicht Demo-Größe), 5 Seeds
Aufruf:  python tools/messreihe.py <teil> [--shard K/N] [--workers 3] [--limit 30]
Jede Lösung (Regel und CP-SAT) wird vom unabhängigen Prüfer `ebu_energy.check_plan` geprüft; die Zeile hält fest, ob er sie angenommen hat."""

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ebu_constants as C  # noqa: E402
import ebu_diesel as D  # noqa: E402
import ebu_energy as E  # noqa: E402
import ebu_exact as X  # noqa: E402
import ebu_rules as R  # noqa: E402
import ebu_scenario as S  # noqa: E402

OUT = ROOT / "tools" / "messdaten"
SEASONS = {"Sommer": 1.0, "Winter": C.WINTER_FACTOR}


def grid(part: str):
    if part == "rampe":
        for seed, season, c, p, ch in itertools.product(C.SWEEP_SEEDS, SEASONS, C.RAMP_C, C.RAMP_P, C.CHARGER_OPTIONS):
            yield dict(part=part, timetable="zufall", seed=seed, season=season, c=c, p=p, chargers=ch, slots=C.SLOTS_UNLIMITED)
    elif part == "plaetze":
        for seed, (season, c), p, ch, sl in itertools.product(C.SWEEP_SEEDS, (("Sommer", 60), ("Winter", 80)), (20, 40, 150), C.CHARGER_OPTIONS, (1, 2, C.SLOTS_UNLIMITED)):
            yield dict(part=part, timetable="zufall", seed=seed, season=season, c=c, p=p, chargers=ch, slots=sl)
    elif part == "gemischt":
        for seed, season, c, p, rb in itertools.product(C.SWEEP_SEEDS, SEASONS, (60, 80, 100), (0, 20), (0, 1)):
            yield dict(part=part, timetable="zufall", seed=seed, season=season, c=c, p=p, chargers="beide", slots=C.SLOTS_UNLIMITED, reserve_buses=rb)
    elif part == "takt":
        for seed, season, c, p in itertools.product(C.SWEEP_SEEDS, SEASONS, (60, 80, 100), (0, 10, 20)):
            yield dict(part=part, timetable="takt", seed=seed, season=season, c=c, p=p, chargers="beide", slots=C.SLOTS_UNLIMITED)
    elif part == "tag2":
        for seed, c, p in itertools.product(range(5), (200, 300), (0, 20)):
            yield dict(part=part, timetable="tag2", seed=seed, season="Sommer", c=c, p=p, chargers="beide", slots=C.SLOTS_UNLIMITED)
    elif part == "regeln":
        for seed, season, c, p, ch in itertools.product(range(200), SEASONS, C.RAMP_C, C.RAMP_P, C.CHARGER_OPTIONS):
            yield dict(part=part, timetable="zufall", seed=seed, season=season, c=c, p=p, chargers=ch, slots=C.SLOTS_UNLIMITED)
    elif part == "tag":
        for seed, season, c, p in itertools.product(range(5), SEASONS, (150, 200, 250), (0, 20)):
            yield dict(part=part, timetable="tag", seed=seed, season=season, c=c, p=p, chargers="beide", slots=C.SLOTS_UNLIMITED)
    else:
        raise SystemExit(f"unbekannter Teil: {part}")


def measure(cell: dict, workers: int, limit: float) -> dict:
    if cell["timetable"] == "tag":
        inst = S.generate_day(cell["seed"])
    elif cell["timetable"] == "tag2":
        inst = S.generate_day(cell["seed"], 2)
    else:
        inst = S.generate(cell["seed"], cell["timetable"])
    prm = E.Params(cell["c"], cell["p"], SEASONS[cell["season"]], cell["chargers"], cell["slots"])
    dsl = D.diesel_plan(inst)
    row = dict(cell, n=inst.n, diesel=dsl.buses, layover=inst.layover)
    if cell["part"] == "gemischt":
        budget = dsl.buses + cell["reserve_buses"]
        r = X.solve(inst, prm, budget=budget, time_limit=limit, workers=workers)
        row.update(budget=budget, status=r.status, diesel_buses=r.value, bound=r.bound, seconds=round(r.seconds, 3),
                   check=None if r.plan is None else E.check_plan(inst, prm, r.plan)[0], buses=None if r.plan is None else r.plan.buses)
        return row
    plans = R.all_rules(inst, prm)
    rules_only = cell["part"] == "regeln"
    rules = {}
    ok_rules = True
    for name, plan in plans.items():
        if plan is None:
            rules[name] = None
            continue
        rules[name] = plan.buses
        ok_rules &= E.check_plan(inst, prm, plan)[0]
    for tie in ("frueh", "spaet"):
        pl = R.greedy(inst, prm, "soc_max", tie)
        rules[f"soc_max_{tie}"] = None if pl is None else pl.buses
        if pl is not None:
            ok_rules &= E.check_plan(inst, prm, pl)[0]
    if rules_only:
        row.update(rules=rules, rules_ok=bool(ok_rules))
        return row
    best = R.best_rule({k: v for k, v in plans.items()})
    r = X.solve(inst, prm, time_limit=limit, workers=workers, hint=None if best is None else best[1])
    peak = None
    if r.plan is not None:
        peak = max(E.peak_slots_used(inst, prm, r.plan.charged).values(), default=0)
    row.update(rules=rules, rules_ok=bool(ok_rules), status=r.status, value=r.value, bound=r.bound, seconds=round(r.seconds, 3),
               check=None if r.plan is None else E.check_plan(inst, prm, r.plan)[0], peak_slots=peak)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=float, default=C.MESS_TIME_LIMIT_S)
    ap.add_argument("--skip-first", type=int, default=0, help="die ersten N Zellen des Shards überspringen (ein zweiter Prozess übernimmt das Ende eines langsamen Shards)")
    ap.add_argument("--suffix", default="", help="Dateiname-Zusatz, damit der zweite Prozess eine eigene Datei schreibt")
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split("/"))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{a.part}_{k}{a.suffix}.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done.add(json.dumps({x: r[x] for x in r if x in ("part", "timetable", "seed", "season", "c", "p", "chargers", "slots", "reserve_buses")}, sort_keys=True))
    cells = [c for i, c in enumerate(grid(a.part)) if i % n == k][a.skip_first:]
    t0 = time.time()
    with open(path, "a", encoding="utf-8") as f:
        for i, cell in enumerate(cells):
            if json.dumps(cell, sort_keys=True) in done:
                continue
            f.write(json.dumps(measure(cell, a.workers, a.limit), ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"{a.part} {k}/{n}: {i + 1}/{len(cells)} nach {time.time() - t0:.0f} s", flush=True)
    print(f"{a.part} {k}/{n} fertig nach {time.time() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()
