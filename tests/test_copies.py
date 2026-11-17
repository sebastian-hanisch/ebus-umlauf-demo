"""Die aus `fahrzeugflotte-demo` kopierte Dieselbasis (`max_matching`: Mindestflotte = n − Matching) ist bewacht.

Drei Wächter: (1) der Quelltext der Funktion hat einen festen Hash (die Kopie wird nicht unbemerkt geändert), (2) wo der Nachbarordner vorhanden ist, ist der
Quelltext Zeichen für Zeichen derselbe wie dort, (3) feste Referenzwerte, die mit der Funktion in `fahrzeugflotte-demo/fz_dispatch.py` erzeugt wurden."""

import ast
import hashlib
from pathlib import Path

import pytest

import ebu_diesel as D

ROOT = Path(__file__).resolve().parent.parent
SOURCE_HASH = "bda55b06aed08dd8b7601ec26e4d218285b38fd10c31df8af57c86ca56ba321f"   # SHA-256 des Quelltexts von max_matching in fz_dispatch.py (2026-11-17)


def _function_source(path: Path, name: str) -> str:
    src = path.read_text(encoding="utf-8")
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, node)


def test_copy_has_the_hash_of_the_original():
    assert hashlib.sha256(_function_source(ROOT / "ebu_diesel.py", "max_matching").encode("utf-8")).hexdigest() == SOURCE_HASH


def test_copy_equals_the_original_where_the_neighbour_folder_exists():
    original = ROOT.parent / "fahrzeugflotte-demo" / "fz_dispatch.py"
    if not original.exists():
        pytest.skip("fahrzeugflotte-demo liegt nicht neben diesem Ordner")
    assert _function_source(original, "max_matching") == _function_source(ROOT / "ebu_diesel.py", "max_matching")


def test_reference_values_from_the_original():
    assert D.max_matching(6, [[1, 2], [2, 3], [3], [4], [], [1]]) == (4, [-1, 0, 1, 2, 3, -1])
    assert D.max_matching(6, [[3, 4], [3], [3, 4, 5], [], [5], []]) == (3, [-1, -1, -1, 1, 0, 2])
    adj = [[7], [5, 7], [4, 5, 6], [4, 6, 8], [5, 7, 8], [8], [], [], []]
    assert D.max_matching(9, adj) == (5, [-1, -1, -1, -1, 3, 1, 2, 0, 4])


def test_splitmix64_stream_is_the_portfolio_standard():
    """`ebu_rng.py` ist die Vorlage `tools/templates/rng_splitmix64_exact.py` des Website-Repos; derselbe Strom wie in `dc-standort-demo/tests/test_copies.py`."""
    from ebu_rng import SplitMix64
    rng = SplitMix64(1)
    assert [rng.next_u64() for _ in range(3)] == [10451216379200822465, 13757245211066428519, 17911839290282890590]
