# Elektrobus-Umlauf: Wie viele Busse braucht das Laden? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-ebus-umlauf-demo.streamlit.app/)**

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`; Themenseite „Energie und Elektromobilität optimieren“ in Vorbereitung). Eine **Buslinie mit zwei Endhaltepunkten und höchstens {{ C.MAX_TRIPS }} Fahrten** (bewusst **Demo-Größe**: dort beweist der exakte Löser die meisten Zellen in Sekunden, ohne Laden und mit kleiner Batterie bleibt der Beweis oft aus): Wie viele Busse braucht der Umlauf, wenn die Busse elektrisch fahren, eine Batteriegrenze haben und in den Wendezeiten an den Endhaltepunkten laden? Die Demo vergleicht den **Dieselumlauf** (ohne Batteriegrenze, exakt und mit Beweis), **einfache Regeln** und ein **exaktes Verfahren** (CP-SAT) mit Beweis-Status, und beantwortet vier Fragen: den **Aufschlag** je Batterie und Ladeleistung, die **Ladeplätze** am Endhaltepunkt, den Abstand der Regeln zum **bewiesenen Optimum** und die Zahl der **Dieselbusse bei fester Flottengröße**.

**Fahrpläne, Verbrauch, Winterfaktor und Ladeverhalten sind Annahmen eines Generators, keine echten Daten.** Alle Zahlen unten sind Messungen mit dem Code dieser Demo (Rohdaten in `tools/messdaten/`, Auswertung `tools/messreihe_auswertung.py`, Bericht `tools/MESSBERICHT.md`).

## Warum dieses Problem

Ein Dieselbus fährt, bis der Fahrplan zu Ende ist; die kleinste Zahl von Bussen, die alle Fahrten eines Fahrplans bedient, ist die **minimale Wegeüberdeckung** und folgt aus einem maximalen Matching (n minus Matching). Ein Elektrobus hat eine Batterie: Ketten von Fahrten, die ein Dieselbus fährt, sind für ihn zu lang, er muss in den Wendezeiten laden oder wird durch einen zweiten Bus ersetzt. Dass das mehr Busse kostet, ist bekannt. Offen für jemanden, der einen Fahrplan elektrifizieren will, ist das **Wie viel**: Wie groß ist der Aufschlag bei welcher Batterie und Ladeleistung, was kostet es, wenn nur ein Bus gleichzeitig laden darf, wie weit liegt die einfache Regel („nimm den Bus mit dem höchsten Ladestand“) vom Optimum, und wie viele Dieselbusse bleiben, wenn die Flotte nicht wachsen darf?

**Abgrenzung zu den Nachbarn:** Die Dieselbasis (n minus Matching) ist dasselbe Modell wie in `fahrzeugflotte-demo` (Hafen; dort steht „Laden am Kran“ unter „Bewusst nicht umgesetzt“) und wird von dort wörtlich übernommen (`tests/test_copies.py`); neu sind die Batteriegrenze, das Laden in der Wendezeit, die Ladeplätze und die gemischte Flotte. `ladestrategie-demo` rechnet **ein** Fahrzeug auf **einer** Strecke (Ladestopps, Kälte, Ladekurve), `transit-demo` das Liniennetz ohne Umlauf: beide kennen keinen Fahrplan mit mehreren Bussen.

## Modell (Annahmen)

* **Fahrplan:** eine Linie, zwei Endhaltepunkte A und B, Fahrten von 6:00 bis 13:00 Uhr in beiden Richtungen. Der Generator (SplitMix64, `ebu_scenario.py`) zieht aus dem Zufalls-Seed die Linienlänge (6 bis 10 km Luftlinie, Umwegfaktor 1,25), die Geschwindigkeit (16 bis 22 km/h, in der Spitze 6:30 bis 9:00 Uhr mal 0,85), den Takt in der Spitze (12 oder 15 min), außerhalb (24 oder 30 min) und den Versatz der Gegenrichtung. Er erzeugt {{ d['meta']['rampe']['n_min'] }} bis {{ d['meta']['rampe']['n_max'] }} Fahrten (Zufalls-Seeds 0 bis 9); das Höchstmaß {{ C.MAX_TRIPS }} belegt ein Test über 3.000 Zufalls-Seeds.
* **Anschluss:** Fahrt j darf auf Fahrt i folgen, wenn die Wartezeit für die Mindest-Wendezeit ({{ C.LAYOVER_MIN }} min) und, bei verschiedenen Endhaltepunkten, eine **Leerfahrt** (25 km/h, derselbe Verbrauch) reicht; höchstens {{ C.MAX_IDLE_MIN }} min Wartezeit.
* **Energie:** {{ f1(C.KWH_PER_KM) }} kWh/km, Reserve {{ int(C.RESERVE_FRACTION * 100) }} % von C (nutzbar sind 90 %), jeder Bus startet voll, **Winter** = Verbrauch mal {{ str(C.WINTER_FACTOR).replace('.', ',') }}, also +36 % (Annahme; `ladestrategie-demo` liest den Wintertestwert AAA, 35,6 % bei −6,6 °C, als Mehrverbrauch; ein Effizienzverlust von 35,6 % ergäbe mal 1,55, der Faktor ist also eher niedrig angesetzt; Quelle nur über ein Suchergebnis gesehen). Die Ladeleistung bleibt gleich.
* **Laden:** linear bis C (keine Ladekurve), nur in der Wartezeit nach Abzug von Wendezeit, Leerfahrt und {{ C.CHARGE_OVERHEAD_MIN }} min An- und Abstecken; an beiden Endhaltepunkten oder nur an A. **Ladeplätze:** ein Ladevorgang belegt einen Platz die ganze Wartezeit am Haltepunkt (Annahme).
* **Dieselbus:** keine Energiegrenze. **Gemischte Flotte:** je Kette Diesel oder Elektro, höchstens F Busse insgesamt, möglichst wenige Dieselbusse.
* Formeln: Expander „📐 Mathematische Formulierung“ der App.

## Methodik

* **Dieselumlauf** (Referenz): n minus maximales Matching; Beweis durch eine Knotenüberdeckung gleicher Größe (Satz von König), `verify_diesel_proof` prüft sie ohne Löser.
* **Vier Regeln** (Fahrten in Abfahrtsreihenfolge, unter den möglichen Bussen wählen, sonst neuer Bus): **Spät** (kürzeste Standzeit), **Früh** (längste Standzeit), **Ladestand max.**, **Ladestand min.**; dazu die naheliegende Heuristik **Dieselplan, dann trennen** (ohne Quelle für den Praxiseinsatz) (Dieselumlauf elektrifizieren, Kette trennen, wo die Batterie nicht reicht). Der Gleichstand beim Ladestand ist wählbar (Einsatzreihenfolge, früh, spät).
* **Exakt (CP-SAT):** je Anschluss eine Ja/Nein-Variable, je Fahrt der Ladestand, bei begrenzten Plätzen je Anschluss die Entscheidung „laden“ mit einem Zeitraum und `AddCumulative` je Haltepunkt; Zeitlimit, höchstens {{ C.EXACT_WORKERS }} Arbeiter, beste Regel als Startlösung. **Ohne Beweis** steht die Zahl als obere Schranke („nicht bewiesen“) mit der bewiesenen unteren Schranke, nie als Optimum. Verbrauch wird auf 0,01 kWh auf-, Ladung abgerundet (die Rundung geht zu Lasten des Modells).
* **Prüfer** (`ebu_energy.check_plan`): rechnet jede Lösung (Regel oder CP-SAT) in Fließkomma nach, einschließlich der Plätze, ohne die Rundung des Lösers und unabhängig von den Löservariablen; er teilt sich mit dem Löser aber die Definitionen von Energie, Laden und Anschlüssen (die Modelldefinition prüft das Aufzählungs-Orakel mit eigener Physik, siehe „Verifikation“). Abgelehnt: {{ d['meta']['rampe']['rejected'] + d['meta']['plaetze']['rejected'] + d['meta']['takt']['rejected'] + d['meta']['gemischt']['rejected'] }} von {{ num(d['meta']['rampe']['rows'] + d['meta']['plaetze']['rows'] + d['meta']['takt']['rows'] + d['meta']['gemischt']['rows']) }} Zeilen der Messreihen (jede mit der exakten Lösung; die {{ d['meta']['gemischt']['rows'] }} Zeilen der gemischten Flotte ohne Regeln, die übrigen mit allen Regeln).
* **Monotone Hülle:** Ein Umlauf, der mit weniger Batterie, Ladeleistung, Ladern oder Plätzen oder mehr Verbrauch zulässig ist, ist auch mit mehr zulässig. Die Auswertung setzt die beste bekannte Zahl jeder Zelle auf das Minimum über alle schwächeren Zellen und die untere Schranke auf das Maximum über alle stärkeren. Sie verbesserte in dieser Messreihe die oberen Schranken in {{ d['meta']['rampe']['hull_improved'] + d['meta']['plaetze']['hull_improved'] + d['meta']['takt']['hull_improved'] }} Zellen und machte {{ (d['meta']['rampe']['proven_hull'] - d['meta']['rampe']['proven_raw']) + (d['meta']['plaetze']['proven_hull'] - d['meta']['plaetze']['proven_raw']) + (d['meta']['takt']['proven_hull'] - d['meta']['takt']['proven_raw']) }} Zelle(n) zusätzlich beweisbar (untere Schranke einer stärkeren Zelle).

## Befunde (gemessen, keine Behauptungen)

Messreihe: Zufalls-Seeds 0 bis 9 (je Zelle zehn Fahrpläne), Zeitlimit {{ int(d['meta']['time_limit']) }} s je Rechnung auf dem Entwicklungsrechner (auf anderen Rechnern kann eine Zelle anders ausgehen); „≤“ vor einer Zahl: nicht in allen zehn Fahrplänen bewiesen, dann obere Schranke. Aufschlag = Elektro-Umlauf minus Dieselumlauf, in Bussen, Mittel über die zehn Fahrpläne.

| Frage | Befund | Beleg |
|---|---|---|
| **Wie groß ist der Aufschlag?** | Eine **Rampe über die Batterie**; über die Ladeleistung fällt der Aufschlag schon zwischen 0 und 10 kW stark (das Raster ist dort grob, ob dazwischen ein Sprung liegt, ist nicht gemessen). Sommer, Lader an beiden Endhaltepunkten, C = 60 kWh: {{ rc('Sommer','beide',60,0) }} ohne Laden ({{ rp('Sommer','beide',60,0) }} Fahrplänen bewiesen, mittlere bewiesene untere Schranke {{ rl('Sommer','beide',60,0) }}), {{ rc('Sommer','beide',60,10) }} bei 10 kW, {{ rc('Sommer','beide',60,20) }} bei 20 kW, {{ rc('Sommer','beide',60,40) }} bei 40 kW (je {{ rp('Sommer','beide',60,10) }} bewiesen). Bei C = 120 kWh ist der Aufschlag in allen vier Ladeleistungen {{ rc('Sommer','beide',120,0) }} ({{ rp('Sommer','beide',120,0) }} bewiesen). | `test_claims.py::test_ramp_*` |
| **Was ändert der Winter?** | Winter, C = 60 kWh, Lader an beiden: {{ rc('Winter','beide',60,10) }} bei 10 kW ({{ rp('Winter','beide',60,10) }} bewiesen) gegen {{ rc('Sommer','beide',60,10) }} im Sommer; {{ rc('Winter','beide',60,20) }} bei 20 kW gegen {{ rc('Sommer','beide',60,20) }}. Im Raster (Mittel je Zelle, {{ d['fakten']['winter']['cells'] }} Zellen aus Batterie, Ladeleistung und Ladersetzung) ist der Winter-Aufschlag in {{ d['fakten']['winter']['larger'] }} Zellen größer als der Sommer-Aufschlag (in {{ d['fakten']['winter']['fully_proven_larger'] }} von {{ d['fakten']['winter']['fully_proven_cells'] }} Zellen, in denen beide Jahreszeiten voll bewiesen sind), in {{ d['fakten']['winter']['smaller'] }} kleiner (das folgt aus der Monotonie der Hülle und ist kein Messergebnis). Ohne Laden gilt exakt: **Winter bei C kWh = Sommer bei C/1,36 kWh** (Aufzählung auf 30 Mini-Instanzen, 30 von 30 gleich; nur für P = 0). | `test_claims.py::test_winter_*`, `test_oracle_ebus_umlauf.py::test_winter_*` |
| **Wo endet die Rampe?** | Ohne Laden (P = 0, Lader an beiden, {{ d['fakten']['kettenenergie']['p0_rows'] }} Zeilen): In den {{ d['fakten']['kettenenergie']['sufficient'] }} Zeilen, in denen die nutzbare Batterie (90 % von C) die Energie der energiereichsten Dieselkette deckt (diese Ketten brauchen {{ round(d['fakten']['kettenenergie']['sufficient_kwh_min']) }} bis {{ round(d['fakten']['kettenenergie']['sufficient_kwh_max']) }} kWh; über alle Instanzen und beide Jahreszeiten {{ round(d['fakten']['kettenenergie']['chain_kwh_min']) }} bis {{ round(d['fakten']['kettenenergie']['chain_kwh_max']) }} kWh), ist der Aufschlag {{ d['fakten']['kettenenergie']['sufficient_zero'] }} von {{ d['fakten']['kettenenergie']['sufficient'] }} Mal 0 (bewiesen, der Dieselumlauf selbst ist dann fahrbar). In den {{ d['fakten']['kettenenergie']['insufficient'] }} übrigen Zeilen liegt die beste bekannte Zahl in {{ d['fakten']['kettenenergie']['insufficient_positive'] }} über dem Dieselumlauf ({{ d['fakten']['kettenenergie']['insufficient_positive_proven'] }} davon bewiesen positiv); in {{ d['fakten']['kettenenergie']['insufficient_zero_proven'] }} ist der Aufschlag bewiesen 0, obwohl die Batterie für die Dieselkette nicht reicht. | `test_claims.py::test_chain_energy_*` |
| **Hilft ein zweiter Lader?** | Lader nur am Endhaltepunkt A statt an beiden: in {{ d['fakten']['lader']['pairs'] }} beiderseits bewiesenen Paaren mit Laden (Rampe-Raster ohne die {{ d['fakten']['lader_ohne_laden'] }} Paare mit P = 0, in denen die Lader gleichgültig sind) mehr Busse in {{ d['fakten']['lader']['worse'] }}, gleich viele in {{ d['fakten']['lader']['same'] }} (weniger Busse mit weniger Ladern kann nicht vorkommen, die 0 ist kein Messergebnis); mittlerer Aufschlag {{ f1(d['fakten']['lader']['mean_b']) }} statt {{ f1(d['fakten']['lader']['mean_a']) }} Bussen; nur die leichteren, beweisbaren Zellen. | `test_claims.py::test_chargers_*` |
| **Sind die Ladeplätze ein Engpass?** | Bei gleicher Ladeleistung kostet ein Platz je Endhaltepunkt Busse. Mittel über zehn Fahrpläne (Sommer, C = 60 kWh, Lader an beiden Endhaltepunkten), Aufschlag bei 1 / 2 / unbegrenzten Plätzen: 20 kW {{ pc('Sommer',60,20,'beide',1) }} / {{ pc('Sommer',60,20,'beide',2) }} / {{ pc('Sommer',60,20,'beide',99) }}, 40 kW {{ pc('Sommer',60,40,'beide',1) }} / {{ pc('Sommer',60,40,'beide',2) }} / {{ pc('Sommer',60,40,'beide',99) }}, 150 kW {{ pc('Sommer',60,150,'beide',1) }} / {{ pc('Sommer',60,150,'beide',2) }} / {{ pc('Sommer',60,150,'beide',99) }}; mit Lader nur an A bei 40 kW {{ pc('Sommer',60,40,'nur A',1) }} / {{ pc('Sommer',60,40,'nur A',2) }} / {{ pc('Sommer',60,40,'nur A',99) }}. Bewiesen sind {{ d['fakten']['plaetze_bewiesen']['1'][0] }} von {{ d['fakten']['plaetze_bewiesen']['1'][1] }} Zeilen mit einem Platz, {{ d['fakten']['plaetze_bewiesen']['2'][0] }} von {{ d['fakten']['plaetze_bewiesen']['2'][1] }} mit zwei und {{ d['fakten']['plaetze_bewiesen']['99'][0] }} von {{ d['fakten']['plaetze_bewiesen']['99'][1] }} mit unbegrenzten Plätzen: die Zahlen mit „≤“ sind obere Schranken, der wahre Mittelwert kann niedriger sein. Nur in beiderseits bewiesenen Paaren (ein Platz gegen unbegrenzt, {{ d['fakten']['plaetze_1']['pairs'] }} Paare, bevorzugt die leichten Zellen): mehr Busse in {{ d['fakten']['plaetze_1']['worse'] }}, gleich viele in {{ d['fakten']['plaetze_1']['same'] }}, weniger in {{ d['fakten']['plaetze_1']['better'] }}; mittlerer Aufschlag {{ f1(d['fakten']['plaetze_1']['mean_b']) }} statt {{ f1(d['fakten']['plaetze_1']['mean_a']) }}. Zwei Plätze gegen unbegrenzt: mehr Busse in {{ d['fakten']['plaetze_2']['worse'] }} von {{ d['fakten']['plaetze_2']['pairs'] }} Paaren. Bei 150 kW fällt der Platz weniger ins Gewicht, verschwindet aber nicht: ein Platz gegen unbegrenzt, mehr Busse in {{ d['fakten']['plaetze_1_nach_p']['150']['worse'] }} von {{ d['fakten']['plaetze_1_nach_p']['150']['pairs'] }} bewiesenen Paaren (20 kW: {{ d['fakten']['plaetze_1_nach_p']['20']['worse'] }} von {{ d['fakten']['plaetze_1_nach_p']['20']['pairs'] }}, 40 kW: {{ d['fakten']['plaetze_1_nach_p']['40']['worse'] }} von {{ d['fakten']['plaetze_1_nach_p']['40']['pairs'] }}). | `test_claims.py::test_slots_*` |
| **Wie weit liegen einfache Regeln vom Optimum?** | siehe den Absatz „Regeln“ unter der Tabelle | `test_claims.py::test_rules_*` |
| **Wie viele Dieselbusse bleiben bei fester Flotte?** | Flotte = Dieselmindestflotte (Lader an beiden, unbegrenzte Plätze, Batterie 60, 80 und 100 kWh, P = 0 und 20 kW, Sommer und Winter, {{ d['fakten']['gemischt']['rows'] }} Zeilen, {{ d['fakten']['gemischt']['proven'] }} bewiesen): im Mittel {{ f1(d['fakten']['gemischt']['reserve0_mean']) }} Dieselbusse (alle {{ d['fakten']['gemischt']['reserve0_proven'] }} Zeilen bewiesen); mit einem Bus Reserve ≤ {{ f1(d['fakten']['gemischt']['reserve1_mean']) }} (obere Schranke; mittlere untere Schranke {{ f1(d['fakten']['gemischt']['reserve1_lb_mean']) }}; {{ d['fakten']['gemischt']['reserve1_proven'] }} von 120 Zeilen bewiesen). Mit Reserve 1 sinkt die Zahl der Dieselbusse (beste bekannte Zahlen) in {{ d['fakten']['gemischt']['reserve_helps'] }} von {{ d['fakten']['gemischt']['reserve_pairs'] }} Paaren. Beispiele (Mittel, Reserve 0): Winter, C = 60, 20 kW: {{ f1(d['gemischt']['Winter|60|20|0']['mean']) }}; Sommer, C = 60, 20 kW: {{ f1(d['gemischt']['Sommer|60|20|0']['mean']) }}. | `test_claims.py::test_hybrid_*` |
| **Gilt das auch im Takt-Fahrplan?** | Preset „Gleichmäßiger Takt“ (20 min, Wendezeit mindestens 10 % der Fahrzeit und mindestens 5 min, hier {{ d['fakten']['takt_gegen_zufall']['Sommer|60|10']['takt_layover'][0] }} min, {{ int(d['fakten']['takt_gegen_zufall']['Sommer|60|10']['takt_n']) }} Fahrten, Dieselumlauf {{ d['meta']['takt']['diesel_min'] }} bis {{ d['meta']['takt']['diesel_max'] }} Busse; ein Fahrplan, der Zufalls-Seed verschiebt nur den Versatz): Aufschlag Sommer, C = 60, 10 kW ≤ {{ f1(d['fakten']['takt_gegen_zufall']['Sommer|60|10']['takt']) }} ({{ d['fakten']['takt_gegen_zufall']['Sommer|60|10']['takt_proven'] }} von 10 bewiesen, mittlere untere Schranke {{ f1(d['fakten']['takt_gegen_zufall']['Sommer|60|10']['takt_lb']) }}; Generator-Fahrpläne: {{ f1(d['fakten']['takt_gegen_zufall']['Sommer|60|10']['zufall']) }}), 20 kW ≤ {{ f1(d['fakten']['takt_gegen_zufall']['Sommer|60|20']['takt']) }} ({{ d['fakten']['takt_gegen_zufall']['Sommer|60|20']['takt_proven'] }} von 10 bewiesen; Generator: {{ f1(d['fakten']['takt_gegen_zufall']['Sommer|60|20']['zufall']) }}). Annahme-Fahrplan, kein echter. | `test_claims.py::test_takt_*` |
| **Wie schnell ist der Beweis?** | Median {{ f1(d['fakten']['zeit']['median']) }} s je exakter Rechnung in dieser Messkonfiguration (3 Arbeiter je Lösung, mehrere Prozesse gleichzeitig; ob eine Zelle im Zeitlimit bewiesen wird, hängt vom Lauf ab) ({{ num(d['fakten']['zeit']['rows']) }} Zeilen Rampe und Ladeplätze); {{ d['fakten']['zeit']['proven_under_1s'] }} von {{ d['fakten']['zeit']['proven_rows'] }} bewiesenen Zeilen in höchstens 1 s, {{ d['fakten']['zeit']['proven_under_5s'] }} in höchstens 5 s. In der Rampe sind {{ d['meta']['rampe']['proven_raw'] }} von {{ d['meta']['rampe']['rows'] }} Zeilen bewiesen; bei {{ d['meta']['rampe']['positive'] }} Zeilen liegt die obere Schranke über dem Dieselumlauf, davon {{ d['meta']['rampe']['positive_proven'] }} bewiesen; **ohne Laden und mit kleiner Batterie bleibt der Beweis oft aus** (Sommer, C = 60, 0 kW: {{ rp('Sommer','beide',60,0) }} Fahrplänen bewiesen). | `test_claims.py::test_proof_*` |

### Regeln gegen das bewiesene Optimum

{{ T.regeln_markdown(d) }}

### Befunde, die sich gegenüber der Vormessung nicht bestätigt haben

Die Vormessung zu dieser Demo (zwei Linien, Tagesmaßstab, anderer Generator) vermutete zwei Wirkungen (der Gleichstandsbruch kippt die Regel; Regeln werden mit mehr Ladeleistung oft schlechter), die in der Demo-Größe nur schwach wiederkehren: (1) **Der Gleichstandsbruch kippt die Regel kaum:** er ändert die Busanzahl von „Ladestand max.“ nur in {{ d['regeln']['grosse_reihe']['tie_differ'] }} von {{ num(d['regeln']['grosse_reihe']['tie_rows']) }} Zeilen. (2) **Regeln werden mit mehr Ladeleistung oder Batterie nur selten schlechter** (oben: höchstens {{ pct(max(max(v['c'][0], v['p'][0]) for k, v in d['regeln']['grosse_reihe']['nonmono'].items() if k in ('spaet', 'frueh', 'soc_max', 'soc_min')), 9600) }} der Zellpaare je Regel und Richtung). Beides sind Aussagen über diese Demo-Größe; ob sie im Tagesmaßstab anders ausfallen, ist hier nicht gemessen. Die Vormessung fand im Tagesmaßstab (zwei Linien, rund 200 Fahrten) keinen beweisbaren positiven Aufschlag; mit dem Generator dieser Demo ist der Beweis bei einer Linie und {{ d['tag']['n_min'] }} bis {{ d['tag']['n_max'] }} Fahrten in {{ d['tag']['positive_proven'] }} von {{ d['tag']['positive'] }} Zeilen mit Aufschlag gelungen, bei {{ d['tag2']['n_min'] }} bis {{ d['tag2']['n_max'] }} Fahrten in {{ d['tag2']['positive_proven'] }} von {{ d['tag2']['positive'] }} (Zeitlimit {{ int(d['tag']['time_limit']) }} s).

## Ehrliche Grenzen

{{ T.grenzen_markdown(d) }}

## Verifikation

{{ tests }} Tests (`python -m pytest tests/ -n 8`), zusammengesetzt aus:

* **Orakel** (`tests/test_oracle_ebus_umlauf.py`): der exakte Löser gegen die **vollständige Aufzählung** aller Zerlegungen in Ketten mit eigener, neu geschriebener Physik (Mini-Instanzen bis 7 Fahrten, zwei Familien: Zufall und Takt; mit und ohne Platzgrenze, mit Teilmengen-Aufzählung der Ladeentscheidungen) und die gemischte Flotte gegen Aufzählung; Dieselbasis gegen networkx (Hopcroft-Karp) und gegen Aufzählung; Monotonie des bewiesenen Optimums; der Prüfer lehnt von Hand gebaute unzulässige Pläne ab. **Großer Lauf (Scratch, `tools/oracle_scratch.py`):** {{ sum(v['verglichen'] for v in oracle['elektro'].values()) }} Mini-Instanzen für den Elektro-Umlauf und {{ sum(v['verglichen'] for v in oracle['gemischt'].values()) }} Fälle der gemischten Flotte verglichen, {{ sum(v['abweichungen'] for v in oracle['elektro'].values()) + sum(v['abweichungen'] for v in oracle['gemischt'].values()) }} Abweichungen; die Ladeplatzgrenze ändert das Optimum in {{ sum(v['platzgrenze_wirkt'] for v in oracle['elektro'].values()) }} dieser Fälle (nur dort prüft die Aufzählung sie wirklich).
* **Kern** (`test_algorithm.py`, `test_edge_cases.py`): Handrechnung auf der Mini-Instanz (Anschlüsse, Dieselumlauf, Ladegewinn, Platzintervalle, jede Regel, exakter Löser), Randfälle (eine und zwei Fahrten, Fahrt allein nicht fahrbar, inklusive Grenze der nutzbaren Batterie, keine Anschlüsse, Gleichstandsbruch, Platzgrenze, gemischte Flotte).
* **Kopie aus `fahrzeugflotte-demo`** (`test_copies.py`): Hash, Quelltextvergleich und feste Referenzwerte der Dieselbasis; SplitMix64-Strom.
* **Hilfsmodule neu laden** (`modul_frisch.py`, `test_modul_frisch.py`): nach einem Update mit geänderten Hilfsmodulen lädt die laufende App sie neu (Vorlage aus `taktik-muster-demo`).
* **Messreihen** (`test_messreihe.py`): jede Messreihe deckt ihr Raster genau einmal ab, der Prüfer lehnte nichts ab, der Löser ist nie schlechter als die beste Regel, Nullspalten (jede Variante weicht irgendwo von der Nachbarvariante ab), Kreuzprobe Ladeplatz-Modell gegen Modell ohne Platzgrenze, JSON gegen frische Auswertung der Rohdaten.
* **Aussagen** (`test_claims.py`): jede Zahl dieser README wird aus `data/messreihe.json` gebaut (`tools/readme_bauen.py`), die README ist genau das Ergebnis dieses Baus; dazu Eigenschaftstests der Aussagen (Rampe monoton, Hülle, Lader, Plätze, Regeln, Dieselketten).
* **Verdikte** (`test_verdicts.py`): jeder Zweig und jede Zahl der Urteilstexte an handgesetzten Werten; je Preset das erwartete Urteil (`test_claims.py::test_preset_*`).
* **Oberfläche** (`test_app*.py`, `test_layout.py`, `test_footer.py`, `test_visualization.py`): jede Taste, jeder Regler an Minimum und Maximum, alle Auswahlregler, die vier Kernfragen mit ihren Knöpfen, Permalink (begrenzt und rastet ein), Schnellstart in der Seitenleiste und Hervorhebung, Figuren gegen die Daten.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `app.py` | Streamlit-App: Ergebnis, vier Kernfragen, Methodenvergleich, Grenzen, Formeln |
| `ebu_constants.py` | Regler-Grenzen, feste Annahmen, Presets |
| `ebu_scenario.py` | Fahrplan-Generator (Zufalls-Seed, gleichmäßiger Takt), Fahrtengraph |
| `ebu_diesel.py` | Dieselumlauf = n − Matching mit König-Beweis (`max_matching` aus `fahrzeugflotte-demo` kopiert) |
| `ebu_energy.py` | Energiemodell, Ladeplatz-Intervalle, unabhängiger Fließkomma-Prüfer |
| `ebu_rules.py` | Regeln und „Dieselplan, dann trennen“ |
| `ebu_exact.py` | CP-SAT: Elektro-Umlauf, Ladeplätze, gemischte Flotte |
| `ebu_evaluation.py` | Einstellungen, Analyse, Rampe und Ladeplätze live, Verdikte |
| `ebu_texte.py` | Textbausteine aus der Messreihe (App und README) |
| `ebu_visualization.py` | Umlauf-Gantt, Heatmap, Regeln (Achsen fest) |
| `ebu_presets.py`, `ebu_layout.py`, `ebu_rng.py`, `modul_frisch.py` | Permalink und Presets, fester Kopf, Zufallsquelle, Neuladen geänderter Hilfsmodule |
| `data/messreihe.json` | ausgewertete Messreihe (von der App gelesen) |
| `tools/messreihe.py`, `tools/messreihe_auswertung.py`, `tools/messbericht.py` | Messreihen, Auswertung (monotone Hülle), Messbericht `tools/MESSBERICHT.md` |
| `tools/messdaten/` | Rohdaten (eine Zeile je Rechnung) |
| `tools/oracle_scratch.py`, `tools/readme_bauen.py`, `tools/README.vorlage.md` | großer Orakel-Lauf, README-Bau aus der Messreihe |
| `PLAN.md` | Bauplan und Abweichungen vom Auftrag |
| `tests/` | siehe „Verifikation“ |

## Bewusst nicht umgesetzt

* **Realfahrplan, echte Verbrauchsdaten, Ladekurve, Fahrzeitstreuung, Aus- und Einsetzfahrten, Nachtladen, Heizung als Verbraucher** (siehe „Ehrliche Grenzen“).
* **Mehrere Linien und Linienwechsel** (ein Generator mit zwei Linien erlaubte Linienwechsel über Leerfahrten; hier nicht ausgewertet) und **Gelegenheitsladen an Zwischenhaltestellen**.
* **Benders-artige Zerlegung** für den Tagesmaßstab (Literatur: Alvo et al. beschreiben eine Zerlegung mit begrenzter Zahl paralleler Lader; nur die Zusammenfassung gelesen; hier nur CP-SAT in Demo-Größe).
* **Ladeplatz-Belegung nur während des Ladens** (statt der ganzen Wartezeit) und eine **Messreihe der gemischten Flotte mit Platzgrenze** (die Messreihe rechnet mit unbegrenzten Plätzen; die Live-Rechnung der App nutzt die Platzzahl der Seitenleiste).
* **PDF-Export** des Ergebnisses.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Neu messen: `python tools/messreihe.py rampe --shard 0/4` (und `plaetze`, `gemischt`, `takt`, `tag`, `tag2`, `regeln`; Stunden Rechenzeit), danach `python tools/messreihe_auswertung.py` und `python tools/readme_bauen.py`.

Gebaut mit Streamlit, Plotly, pandas und OR-Tools (CP-SAT).

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zu den Demos: [Interaktive Demos](https://sebastianhanisch.net/demos.html).
