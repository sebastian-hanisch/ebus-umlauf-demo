"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets.

Alle Fahrplan-, Verbrauchs- und Ladeannahmen sind Annahmen dieser Demo (Generator), keine Messdaten: siehe README, Abschnitt „Annahmen“.
Zeit in Minuten, Energie in kWh, Strecken in km."""

# --- feste Annahmen (kein Regler) ------------------------------------------------------------------------------------------------------------
KWH_PER_KM = 1.3            # Verbrauch eines Elektrobusses (Annahme; der Wert der Fahrzeugdaten in `ladestrategie-demo`)
RESERVE_FRACTION = 0.10     # Mindest-Ladestand, Anteil der Batteriekapazität C (Annahme)
LAYOVER_MIN = 3             # Mindest-Wendezeit je Anschluss (min)
CHARGE_OVERHEAD_MIN = 3     # An- und Abstecken bzw. Pantograph-Anfahrt je Ladevorgang (min)
DEADHEAD_KMH = 25.0         # Leerfahrt zwischen den beiden Endhaltepunkten (km/h), Verbrauch wie bei einer Fahrt
MAX_IDLE_MIN = 240          # längste Wartezeit zwischen zwei Fahrten desselben Busses (min)
DETOUR = 1.25               # Umwegfaktor: Strecke = Luftlinie x 1,25
SCALE = 100                 # CP-SAT rechnet ganzzahlig in 0,01 kWh
WINTER_FACTOR = 1.36        # Verbrauchsfaktor Winter: +36 % (Annahme; `ladestrategie-demo` liest den AAA-Wert 35,6 % bei −6,6 °C als Mehrverbrauch; als Effizienzverlust gelesen wären es 1,55)

# --- Fahrplan-Generator ----------------------------------------------------------------------------------------------------------------------
DAY_START_MIN, DAY_END_MIN = 6 * 60, 13 * 60            # betrachtetes Fenster: 6:00 bis 13:00 (Abfahrten)
PEAK_WINDOWS = ((6 * 60 + 30, 9 * 60),)                 # Spitze 6:30 bis 9:00
PEAK_HEADWAYS, OFFPEAK_HEADWAYS = (12, 15), (24, 30)    # Takte (min), je Seed eine Wahl
LENGTH_KM = (6.0, 10.0)                                 # Luftlinie zwischen den Endhaltepunkten (km)
SPEED_KMH = (16.0, 22.0)                                # Reisegeschwindigkeit (km/h); in der Spitze x 0,85
PEAK_SPEED_FACTOR = 0.85
DAY_FULL = (5 * 60, 21 * 60)                            # ganzer Tag für die Grenzmessung (nicht in der App)
PEAK_WINDOWS_FULL = ((6 * 60 + 30, 9 * 60), (15 * 60 + 30, 18 * 60 + 30))
MAX_TRIPS = 50                                          # Demo-Größe: höchstens so viele Fahrten (Test belegt die Obergrenze des Generators)

TIMETABLES = ("zufall", "takt")                         # Fahrplan: Generator mit Spitze, oder gleichmäßiger Takt mit Wendezeit-Regel
TAKT_HEADWAY_MIN = 20                                   # Preset „Gleichmäßiger Takt“: alle 20 min je Richtung
TAKT_LENGTH_KM, TAKT_SPEED_KMH = 8.0, 19.0              # fest im Takt-Fahrplan (Annahme, keine Linie aus echten Daten)
TAKT_TURNAROUND_FRACTION = 0.10                         # Wendezeit mindestens 10 % der Fahrzeit (Annahme; siehe README „Annahmen“)
TAKT_TURNAROUND_MIN_MIN = 5                             # und mindestens 5 min (Annahme)

# --- Regler ----------------------------------------------------------------------------------------------------------------------------------
SEED_MAX, DEFAULT_SEED = 999999, 2
C_MIN, C_MAX, C_STEP, DEFAULT_C = 40, 160, 5, 80        # Batteriekapazität (kWh)
P_MIN, P_MAX, P_STEP, DEFAULT_P = 0, 150, 5, 20         # Ladeleistung am Endhaltepunkt (kW)
SLOT_OPTIONS = (1, 2, 3, 99)                            # Ladeplätze je Endhaltepunkt; 99 = unbegrenzt
SLOTS_UNLIMITED = 99
RESERVE_BUSES_MIN, RESERVE_BUSES_MAX, DEFAULT_RESERVE_BUSES = 0, 3, 0   # Flottengröße = Dieselmindestflotte + Reserve (gemischte Flotte)
CHARGER_OPTIONS = ("beide", "nur A")                    # Lader an beiden Endhaltepunkten oder nur am Endhaltepunkt A
SEASON_OPTIONS = ("Sommer", "Winter")

# --- Rechenzeit ------------------------------------------------------------------------------------------------------------------------------
EXACT_TIME_LIMIT_S = 20.0       # Zeitlimit je exakter Rechnung in der App (Ergebnis wird mit Status „bewiesen“ oder „nicht bewiesen“ gezeigt)
RAMP_TIME_LIMIT_S = 6.0         # Zeitlimit je Zelle der Rampe in der App
EXACT_WORKERS = 4               # höchstens 4 Arbeiter (CP-SAT), auch in den Tests
SWEEP_SEEDS = tuple(range(10))  # feste Instanzen der Messreihe: nie ein einzelner Seed als Befund
MESS_TIME_LIMIT_S = 30.0        # Zeitlimit je Zeile der Messreihe (tools/messreihe.py)

# --- Messraster der Rampe --------------------------------------------------------------------------------------------------------------------
RAMP_C = (60, 80, 100, 120)
RAMP_P = (0, 10, 20, 40)

# --- Farben ----------------------------------------------------------------------------------------------------------------------------------
COLOR_ELECTRIC = "#2F6B65"
COLOR_DIESEL = "#8c6d31"
COLOR_RULE = "#4c78a8"
COLOR_BAD = "#b04a3a"
COLOR_GRID = "rgba(128,128,128,0.35)"

# --- Presets ---------------------------------------------------------------------------------------------------------------------------------
# Schlüssel: seed, c, p, season, chargers, slots, reserve_buses, timetable. Die Zahlen in den Hilfetexten prüft tests/test_claims.py::test_preset_* live.
_BASE = {"seed": 2, "timetable": "zufall", "chargers": "beide", "slots": SLOTS_UNLIMITED, "reserve_buses": 0, "season": "Sommer"}
PRESETS = {
    "Sommer, 60 kWh, 10 kW": {**_BASE, "c": 60, "p": 10},
    "Ohne Laden, 100 kWh": {**_BASE, "c": 100, "p": 0},
    "Winter, nur ein Lader": {**_BASE, "c": 80, "p": 20, "season": "Winter", "chargers": "nur A"},
    "Ein Ladeplatz am Endhaltepunkt": {**_BASE, "c": 60, "p": 40, "slots": 1},
    "Gemischte Flotte im Winter": {**_BASE, "c": 60, "p": 20, "season": "Winter", "reserve_buses": 1},
    "Gleichmäßiger Takt": {**_BASE, "c": 60, "p": 10, "timetable": "takt"},
    "Regel verschlechtert sich mit mehr Batterie": {**_BASE, "seed": 8, "c": 120, "p": 10, "season": "Winter"},
}
DEFAULT_PRESET = "Sommer, 60 kWh, 10 kW"
PRESET_HELP = {
    "Sommer, 60 kWh, 10 kW": "Der Standardfall (Zufalls-Seed 2, 42 Fahrten): kleine Batterie, 10 kW an beiden Endhaltepunkten. Der Dieselumlauf braucht 6 Busse, der Elektro-Umlauf 8, die beste einfache Regel 9.",
    "Ohne Laden, 100 kWh": "Ohne Laden hilft nur die Batterie: Dieselumlauf 6 Busse, Elektro-Umlauf 7, die beste einfache Regel 9.",
    "Winter, nur ein Lader": "Winterverbrauch, Lader nur am Endhaltepunkt A, 80 kWh, 20 kW: Dieselumlauf 6, Elektro-Umlauf 8, die beste einfache Regel 11.",
    "Ein Ladeplatz am Endhaltepunkt": "40 kW, aber nur ein Ladeplatz je Endhaltepunkt: Elektro-Umlauf 7 Busse statt 6 bei unbegrenzten Plätzen (Dieselumlauf 6). In Kernfrage 2 vergleichen.",
    "Gemischte Flotte im Winter": "Winter, 60 kWh, 20 kW, ein Bus Reserve: Die Flotte darf höchstens 7 Busse haben (Dieselmindestflotte 6 plus 1); 2 davon bleiben Diesel. In Kernfrage 4 rechnen; mit 0 Reserve bleiben alle 6 Diesel, mit 2 Reservebussen keiner.",
    "Gleichmäßiger Takt": "Fester Linienfahrplan mit 20-min-Takt und Wendezeit von mindestens 10 % der Fahrzeit und mindestens 5 min (hier 5 min bei 32 min Fahrzeit; Annahme, keine Quelle): Dieselumlauf 5 Busse, Elektro-Umlauf 7, die beste einfache Regel 9.",
    "Regel verschlechtert sich mit mehr Batterie": "Zufalls-Seed 8, Winter, 10 kW, 120 kWh: Die Regel „Spät“ braucht 10 Busse, bei 100 kWh nur 8, während das Optimum von 8 auf 7 sinkt. Batterie auf 100 stellen und in Kernfrage 3 vergleichen.",
}
