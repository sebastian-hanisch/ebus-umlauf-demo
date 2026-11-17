"""Baut README.md aus tools/README.vorlage.md und data/messreihe.json: jede Zahl der README ist ein Ausdruck `{{ ... }}`, der aus der Messreihe gerechnet wird.

Im Ausdruck stehen zur Verfügung: `d` (Inhalt von data/messreihe.json), `T` (ebu_texte: Textbausteine der App), `f1`, `pct`, `C` (Konstanten), `oracle` (tools/messdaten/oracle_scratch.json),
`tests` (Zahl der Tests, Argument), `bw` (Busse als Wort). tests/test_claims.py prüft, dass README.md genau das Ergebnis dieses Baus ist: eine von Hand geänderte oder veraltete Zahl fällt auf.
Aufruf:  python tools/readme_bauen.py [--tests N]      (ohne --tests: Zahl aus README.md übernehmen)"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ebu_constants as C  # noqa: E402
import ebu_texte as T  # noqa: E402

VORLAGE = ROOT / "tools" / "README.vorlage.md"
README = ROOT / "README.md"


def bw(n: int) -> str:
    return "1 Bus" if n == 1 else f"{n} Busse"


def namespace(tests: int) -> dict:
    d = json.loads((ROOT / "data" / "messreihe.json").read_text(encoding="utf-8"))
    oracle = json.loads((ROOT / "tools" / "messdaten" / "oracle_scratch.json").read_text(encoding="utf-8"))

    def cell(table, key):
        return d[table][key]

    def rc(season, chargers, c, p, table="rampe"):
        """Mittlerer Aufschlag einer Zelle der Rampe als Text („≤“ davor, wenn nicht in allen Seeds bewiesen)."""
        x = d[table][f"{season}|{chargers}"][f"{c}|{p}"]
        return ("" if x["proven"] == x["n"] else "≤ ") + T.f1(x["ub_mean"])

    def rp(season, chargers, c, p, table="rampe"):
        x = d[table][f"{season}|{chargers}"][f"{c}|{p}"]
        return f"{x['proven']} von {x['n']}"

    def rl(season, chargers, c, p):
        """Mittlere bewiesene untere Schranke des Aufschlags einer Zelle."""
        return T.f1(d["rampe"][f"{season}|{chargers}"][f"{c}|{p}"]["lb_mean"])

    def pc(season, c, p, chargers, slots):
        """Zelle der Ladeplatz-Messreihe als Text."""
        x = d["plaetze"][f"{season}|{c}|{p}|{chargers}"][str(slots)]
        return ("" if x["proven"] == x["n"] else "≤ ") + T.f1(x["ub_mean"])

    return dict(d=d, T=T, f1=T.f1, pct=T.pct, C=C, oracle=oracle, tests=tests, bw=bw, num=T.num, rc=rc, rp=rp, rl=rl, pc=pc, cell=cell)


def build(tests: int) -> str:
    ns = namespace(tests)
    text = VORLAGE.read_text(encoding="utf-8")
    return re.sub(r"\{\{(.+?)\}\}", lambda m: str(eval(m.group(1).strip(), {"__builtins__": __builtins__}, ns)), text, flags=re.S)


def current_test_count() -> int:
    m = re.search(r"(\d+) Tests", README.read_text(encoding="utf-8")) if README.exists() else None
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", type=int, default=None)
    a = ap.parse_args()
    README.write_text(build(a.tests if a.tests is not None else current_test_count()), encoding="utf-8", newline="\n")
    print("geschrieben:", README)


if __name__ == "__main__":
    main()
