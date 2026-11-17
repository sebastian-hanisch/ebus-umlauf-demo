"""Fahrplan einer Linie (zwei Endhaltepunkte A und B), Fahrtengraph und Energie je Fahrt.

Eine Instanz ist ein Fahrplan: Fahrten mit Abfahrts- und Ankunftszeit, Start- und Endhaltepunkt, Strecke. Ein Bus fährt eine Kette von Fahrten;
auf Fahrt i darf Fahrt j folgen, wenn die Zeit für eine eventuelle Leerfahrt zwischen den Endhaltepunkten und die Mindest-Wendezeit reicht.
Der Fahrtengraph (Anschlüsse) ist azyklisch: i < j in der Abfahrtsreihenfolge. Alles ist Annahme des Generators, keine echten Fahrplandaten."""

import math
from dataclasses import dataclass

import ebu_constants as C
from ebu_rng import SplitMix64


@dataclass(frozen=True)
class Instance:
    seed: int
    timetable: str
    n: int
    start: tuple      # Abfahrt (min) je Fahrt, aufsteigend sortiert
    end: tuple        # Ankunft (min)
    orig: tuple       # Starthaltepunkt: 0 = A, 1 = B
    dest: tuple       # Endhaltepunkt
    dist: tuple       # Strecke (km)
    dh_km: float      # Leerfahrt zwischen A und B (km)
    dh_min: int       # Leerfahrtzeit (min), aufgerundet
    layover: int      # Mindest-Wendezeit je Anschluss (min)
    arcs: tuple       # (i, j, dh_km, slack_min) mit slack = Wartezeit − Leerfahrt − Mindest-Wendezeit >= 0
    length_km: float
    speed_kmh: float


def _ceil_minutes(km: float, kmh: float) -> int:
    return int(math.ceil(km / kmh * 60.0 - 1e-9))


def build_arcs(start, end, orig, dest, dh_km: float, dh_min: int, layover: int = C.LAYOVER_MIN, max_idle: int | None = C.MAX_IDLE_MIN) -> tuple:
    """Alle zulässigen Anschlüsse (i, j): Fahrt j darf auf Fahrt i folgen (Fahrten nach Abfahrt sortiert)."""
    n = len(start)
    arcs = []
    for i in range(n):
        for j in range(i + 1, n):
            gap = start[j] - end[i]
            if max_idle is not None and gap > max_idle:
                break  # alle weiteren j fahren noch später ab
            same = dest[i] == orig[j]
            need = (0 if same else dh_min) + layover
            if gap < need:
                continue
            arcs.append((i, j, 0.0 if same else dh_km, gap - need))
    return tuple(arcs)


def _is_peak(t: int, peaks=C.PEAK_WINDOWS) -> bool:
    return any(a <= t < b for a, b in peaks)


def _trips_from_rows(rows, seed, timetable, length_km, speed_kmh, dist_km, layover=C.LAYOVER_MIN) -> Instance:
    rows = sorted(rows)
    start = tuple(r[0] for r in rows)
    end = tuple(r[1] for r in rows)
    orig = tuple(r[2] for r in rows)
    dest = tuple(1 - o for o in orig)
    dh_min = _ceil_minutes(dist_km, C.DEADHEAD_KMH)
    return Instance(seed, timetable, len(rows), start, end, orig, dest, tuple(dist_km for _ in rows), dist_km, dh_min, layover,
                    build_arcs(start, end, orig, dest, dist_km, dh_min, layover), length_km, speed_kmh)


def generate(seed: int, timetable: str = "zufall") -> Instance:
    """Fahrplan aus dem Zufalls-Seed. `zufall`: Länge, Geschwindigkeit, Takte und Versatz aus dem Seed, Spitze 6:30 bis 9:00 (Takt kürzer,
    Fahrt 15 % langsamer). `takt`: fester Takt und feste Linie, Wendezeit nach der 10-%-Regel (Annahme)."""
    if timetable == "takt":
        return _generate_takt(seed)
    return _generate_zufall(seed, C.DAY_START_MIN, C.DAY_END_MIN, C.PEAK_WINDOWS)


def generate_day(seed: int, headway_divisor: int = 1) -> Instance:
    """Dieselben Annahmen, aber der ganze Tag (5:00 bis 21:00, zwei Spitzen) mit rund 100 Fahrten: nur für die Messung der Grenze (tools/tagesmassstab.py),
    nicht in der App, weil dort der exakte Löser nichts mehr beweist."""
    return _generate_zufall(seed, C.DAY_FULL[0], C.DAY_FULL[1], C.PEAK_WINDOWS_FULL, headway_divisor)


def _generate_zufall(seed: int, t0: int, t1: int, peaks, headway_divisor: int = 1) -> Instance:
    rng = SplitMix64(seed)
    length = C.LENGTH_KM[0] + (C.LENGTH_KM[1] - C.LENGTH_KM[0]) * rng.random()
    d_km = C.DETOUR * length
    v = C.SPEED_KMH[0] + (C.SPEED_KMH[1] - C.SPEED_KMH[0]) * rng.random()
    h_peak = C.PEAK_HEADWAYS[rng.below(len(C.PEAK_HEADWAYS))]
    h_off = C.OFFPEAK_HEADWAYS[rng.below(len(C.OFFPEAK_HEADWAYS))]
    off1 = rng.below(h_off)
    h_peak, h_off = max(1, h_peak // headway_divisor), max(1, h_off // headway_divisor)   # nur für die Grenzmessung mit dichterem Takt
    rows = []
    for direction in (0, 1):
        t = t0 + (off1 if direction else 0)
        while t < t1:
            peak = _is_peak(t, peaks)
            dur = _ceil_minutes(d_km, v * (C.PEAK_SPEED_FACTOR if peak else 1.0))
            rows.append((t, t + dur, direction))
            t += h_peak if peak else h_off
    return _trips_from_rows(rows, seed, "zufall", length, v, d_km)


def takt_turnaround(run_min: int) -> int:
    """Wendezeit der Takt-Regel: mindestens 10 % der Fahrzeit und mindestens 5 min (Annahme)."""
    return max(C.TAKT_TURNAROUND_MIN_MIN, int(math.ceil(C.TAKT_TURNAROUND_FRACTION * run_min - 1e-9)))


def _generate_takt(seed: int) -> Instance:
    """Gleichmäßiger Takt: beide Richtungen fahren alle TAKT_HEADWAY_MIN min. Der Zufalls-Seed verschiebt nur den Versatz der Gegenrichtung
    (um 0 bis zum Takt minus 1 min), damit die Wendezeit nicht für jeden Seed dieselbe ist."""
    rng = SplitMix64(seed)
    d_km = C.DETOUR * C.TAKT_LENGTH_KM
    dur = _ceil_minutes(d_km, C.TAKT_SPEED_KMH)
    off1 = rng.below(C.TAKT_HEADWAY_MIN)
    rows = []
    for direction in (0, 1):
        t = C.DAY_START_MIN + (off1 if direction else 0)
        while t < C.DAY_END_MIN:
            rows.append((t, t + dur, direction))
            t += C.TAKT_HEADWAY_MIN
    return _trips_from_rows(rows, seed, "takt", C.TAKT_LENGTH_KM, C.TAKT_SPEED_KMH, d_km, takt_turnaround(dur))


def fmt_time(t: int) -> str:
    return f"{t // 60:02d}:{t % 60:02d}"


def make_instance(rows, dist_km: float, layover: int = C.LAYOVER_MIN, seed: int = 0) -> Instance:
    """Instanz aus eigenen Fahrten (Abfahrt, Ankunft, Richtung 0 = A→B / 1 = B→A) und einer Streckenlänge; für Tests und Mini-Instanzen."""
    return _trips_from_rows(rows, seed, "eigen", dist_km / C.DETOUR, 0.0, dist_km, layover)
