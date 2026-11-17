"""Großer Orakel-Lauf (DEMO-PLAYBOOK §12: mindestens 200 Zufallsinstanzen im Scratch-Lauf, im Repo nur die kleine Fassung): exakter Löser gegen die Aufzählung
aus tests/test_oracle_ebus_umlauf.py auf Mini-Instanzen beider Familien („zufall“ und „takt“), mit und ohne Ladeplatzgrenze, dazu die gemischte Flotte.

Aufruf:  python tools/oracle_scratch.py      Ergebnis: tools/messdaten/oracle_scratch.json (Zählungen; „Abweichungen“ soll 0 sein)."""

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import ebu_constants as C  # noqa: E402
import ebu_diesel as D  # noqa: E402
import ebu_energy as E  # noqa: E402
import ebu_exact as X  # noqa: E402
import test_oracle_ebus_umlauf as T  # noqa: E402


def main():
    t0 = time.time()
    out = {"elektro": {}, "gemischt": {}}
    for slots in (C.SLOTS_UNLIMITED, 1, 2):
        for family, count, seed in (("zufall", 150, 1), ("takt", 150, 2)):
            rng = random.Random(seed * 1000 + slots)
            cmp = bad = infeasible = surcharge = binding = 0
            for _ in range(count):
                inst, c, p, fw, ch = T._draw_case(rng, family)
                want = T.brute_min_buses(inst, c, p, fw, ch, slots)
                prm = E.Params(c, p, fw, ch, slots)
                got = X.solve(inst, prm, time_limit=20, workers=2)
                if want is None:
                    infeasible += 1
                    bad += got.status not in ("TRIP_INFEASIBLE", "INFEASIBLE")
                    continue
                cmp += 1
                surcharge += want > D.diesel_plan(inst).buses
                if slots < C.SLOTS_UNLIMITED:
                    binding += want > T.brute_min_buses(inst, c, p, fw, ch, C.SLOTS_UNLIMITED)
                bad += not (got.status == "OPTIMAL" and got.value == want and E.check_plan(inst, prm, got.plan)[0])
            out["elektro"][f"{family}|{slots}"] = dict(verglichen=cmp, unzulaessig=infeasible, abweichungen=bad, mit_aufschlag=surcharge, platzgrenze_wirkt=binding)
            print(family, slots, out["elektro"][f"{family}|{slots}"], round(time.time() - t0), flush=True)
    for family, count, seed in (("zufall", 100, 5), ("takt", 100, 6)):
        rng = random.Random(seed)
        cmp = bad = 0
        for _ in range(count):
            inst, c, p, fw, ch = T._draw_case(rng, family)
            d = D.diesel_plan(inst).buses
            for extra in (0, 1, 2):
                want = T.brute_min_diesel(inst, c, p, fw, ch, d + extra)
                got = X.solve(inst, E.Params(c, p, fw, ch), budget=d + extra, time_limit=20, workers=2)
                cmp += 1
                bad += not (got.status == "OPTIMAL" and got.value == want)
        out["gemischt"][family] = dict(verglichen=cmp, abweichungen=bad)
        print("gemischt", family, out["gemischt"][family], round(time.time() - t0), flush=True)
    path = ROOT / "tools" / "messdaten" / "oracle_scratch.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("geschrieben:", path)


if __name__ == "__main__":
    main()
