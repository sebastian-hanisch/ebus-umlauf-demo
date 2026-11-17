# PLAN – ebus-umlauf-demo (Bauplan und Abweichungen)

Stand 2026-11-17. Auftrag: Fall-Demo „Elektrobus-Umlauf: Wie viele Busse braucht das Laden?“ in Demo-Größe (eine Linie, höchstens 50 Fahrten) nach der Vormessung
`energie-planung/messreihe_ebus_umlauf/ERGEBNIS.md` (Ampel gelb, näher an grün).

## Was gebaut ist

* Kern: `ebu_scenario.py` (Fahrplan-Generator, SplitMix64), `ebu_diesel.py` (Dieselumlauf = n − Matching mit König-Beweis; `max_matching` wörtlich aus `fahrzeugflotte-demo`,
  bewacht von `tests/test_copies.py`), `ebu_energy.py` (Energiemodell, unabhängiger Fließkomma-Prüfer), `ebu_rules.py` (vier Regeln, „Dieselplan, dann trennen“, Gleichstandsbruch
  wählbar), `ebu_exact.py` (ein CP-SAT-Modell für Elektro-Umlauf, Ladeplätze und gemischte Flotte).
* App mit vier Kernfragen: Aufschlag (Rampe live und vorgerechnet), Ladeplätze, Regeln gegen das Optimum, gemischte Flotte.
* Messreihen mit `tools/messreihe.py` (Rohdaten `tools/messdaten/`, Auswertung `tools/messreihe_auswertung.py` → `data/messreihe.json`).

## Abweichungen vom Auftrag und ihre Gründe

| Auftrag | Umsetzung | Grund |
|---|---|---|
| Presets im Hauptbereich (OR-Demo-Konvention) | Presets oben in der **Seitenleiste** | DEMO-PLAYBOOK §2 (Stand 2026-10-18, Nutzerentscheidung) ist jünger als die ältere Konvention und gilt „beim Bau“; `new_demo.py` erzeugt es so |
| Exakter Löser im eigenen Tab per Knopf | Das Ergebnis oben rechnet **automatisch** (Spinner, Zeitlimit sichtbar, Cache); der Tab „🧮 Exakt (CP-SAT)“ erklärt Modell und Status | Die Kernzahl der Demo (Busse mit Batterie) wäre ohne die exakte Rechnung leer; Rampe, Ladeplätze und gemischte Flotte bleiben Knöpfe mit Spinner |
| Zahlen der Vormessung | Alles neu gemessen mit dem Generator der Demo (SplitMix64, eine Linie) | Playbook §0: Vormessungszahlen sind Erwartungen; die Vormessung nutzte numpy-PCG64 und zwei Linien in der Hauptreihe |
| Ladeleistungsfaktor 2/3 (Reihe C der Vormessung) | entfällt | Wirkt wie eine kleinere Ladeleistung; die Rampe über P deckt es ab |
| Realistischerer Fahrplan als Preset „falls vertretbar“ | Preset „Gleichmäßiger Takt, Wendezeit-Regel“ (20-min-Takt, Wendezeit mindestens 10 % der Fahrzeit, mindestens 5 min) | **Keine gelesene Quelle** für die 10-%-Regel gefunden (eine Suche, ohne Richtwert); das Preset ist deshalb als Annahme gekennzeichnet, nicht als belegter Realfahrplan. Als Grenze benannt |
| PDF-Export unter dem Diagramm | nicht gebaut | nicht gefordert; das Gerüst führt ihn nur als TODO. In „Bewusst nicht umgesetzt“ |
| Tagesmaßstab als Befund in „Grenzen“ | eigene Messung `tools/messreihe.py tag` (derselbe Generator über 16 Stunden, rund 100 Fahrten, 5 Seeds) | Die Vormessung hatte zwei Linien; die Aussage „kein positiver Aufschlag beweisbar“ gilt für diesen Generator neu zu messen |
| Gemischte Flotte | Live-Rechnung der App nutzt die Platzzahl der Seitenleiste; die Messreihe rechnet mit unbegrenzten Plätzen | Eine Platzgrenze in der Messreihe wurde nicht gemessen (der Prüfer fand den früheren Widerspruch Text/Code, behoben und getestet) |

## Aussagenprüfung (§11a)

Unabhängiger Prüfer (43 Aussagen: 25 belegt, 10 mit Einschränkung, 2 übertrieben, 3 falsch, 3 nicht prüfbar) ohne Kenntnis der Vermutungen des Bauers; alle Befunde eingearbeitet: Code-Widerspruch Kernfrage 4 (Plätze),
obere Schranken ohne „≤“, „kein Sprung“ → „Rampe über die Batterie“, Pflichtwörter zu Winterfaktor (AAA-Wert als Effizienzverlust: ×1,55), Takt-Hilfetext, Lader- und Winterzählung ohne erzwungene Nullen, „Praxis-Heuristik“, „nur dort beweist“.

## Offen für Freigaben (nicht Teil dieses Auftrags)

Commit, GitHub-Repo, Push, Streamlit-Deploy, Website-Einbindung (`add_demo.py`, Footer-Ziel `set_demo_footer.py`, Themenseite „Energie und Elektromobilität“),
Erklärseite, Linux-Prüfung mit Docker (`tools/demo_linux_check.py ebus-umlauf-demo`), `.claude/launch.json`-Eintrag (Port 9871) ist angelegt.
