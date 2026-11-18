# Elektrobus-Umlauf: Wie viele Busse braucht das Laden? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-ebus-umlauf-demo.streamlit.app/)**

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`; Themenseite „Energie und Elektromobilität optimieren“ in Vorbereitung). Eine **Buslinie mit zwei Endhaltepunkten und höchstens 50 Fahrten** (bewusst **Demo-Größe**: dort beweist der exakte Löser die meisten Zellen in Sekunden, ohne Laden und mit kleiner Batterie bleibt der Beweis oft aus): Wie viele Busse braucht der Umlauf, wenn die Busse elektrisch fahren, eine Batteriegrenze haben und in den Wendezeiten an den Endhaltepunkten laden? Die Demo vergleicht den **Dieselumlauf** (ohne Batteriegrenze, exakt und mit Beweis), **einfache Regeln** und ein **exaktes Verfahren** (CP-SAT) mit Beweis-Status, und beantwortet vier Fragen: den **Aufschlag** je Batterie und Ladeleistung, die **Ladeplätze** am Endhaltepunkt, den Abstand der Regeln zum **bewiesenen Optimum** und die Zahl der **Dieselbusse bei fester Flottengröße**.

**Fahrpläne, Verbrauch, Winterfaktor und Ladeverhalten sind Annahmen eines Generators, keine echten Daten.** Alle Zahlen unten sind Messungen mit dem Code dieser Demo (Rohdaten in `tools/messdaten/`, Auswertung `tools/messreihe_auswertung.py`, Bericht `tools/MESSBERICHT.md`).

## Warum dieses Problem

Ein Dieselbus fährt, bis der Fahrplan zu Ende ist; die kleinste Zahl von Bussen, die alle Fahrten eines Fahrplans bedient, ist die **minimale Wegeüberdeckung** und folgt aus einem maximalen Matching (n minus Matching). Ein Elektrobus hat eine Batterie: Ketten von Fahrten, die ein Dieselbus fährt, sind für ihn zu lang, er muss in den Wendezeiten laden oder wird durch einen zweiten Bus ersetzt. Dass das mehr Busse kostet, ist bekannt. Offen für jemanden, der einen Fahrplan elektrifizieren will, ist das **Wie viel**: Wie groß ist der Aufschlag bei welcher Batterie und Ladeleistung, was kostet es, wenn nur ein Bus gleichzeitig laden darf, wie weit liegt die einfache Regel („nimm den Bus mit dem höchsten Ladestand“) vom Optimum, und wie viele Dieselbusse bleiben, wenn die Flotte nicht wachsen darf?

**Abgrenzung zu den Nachbarn:** Die Dieselbasis (n minus Matching) ist dasselbe Modell wie in `fahrzeugflotte-demo` (Hafen; dort steht „Laden am Kran“ unter „Bewusst nicht umgesetzt“) und wird von dort wörtlich übernommen (`tests/test_copies.py`); neu sind die Batteriegrenze, das Laden in der Wendezeit, die Ladeplätze und die gemischte Flotte. `ladestrategie-demo` rechnet **ein** Fahrzeug auf **einer** Strecke (Ladestopps, Kälte, Ladekurve), `transit-demo` das Liniennetz ohne Umlauf: beide kennen keinen Fahrplan mit mehreren Bussen.

## Modell (Annahmen)

* **Fahrplan:** eine Linie, zwei Endhaltepunkte A und B, Fahrten von 6:00 bis 13:00 Uhr in beiden Richtungen. Der Generator (SplitMix64, `ebu_scenario.py`) zieht aus dem Zufalls-Seed die Linienlänge (6 bis 10 km Luftlinie, Umwegfaktor 1,25), die Geschwindigkeit (16 bis 22 km/h, in der Spitze 6:30 bis 9:00 Uhr mal 0,85), den Takt in der Spitze (12 oder 15 min), außerhalb (24 oder 30 min) und den Versatz der Gegenrichtung. Er erzeugt 38 bis 46 Fahrten (Zufalls-Seeds 0 bis 9); das Höchstmaß 50 belegt ein Test über 3.000 Zufalls-Seeds.
* **Anschluss:** Fahrt j darf auf Fahrt i folgen, wenn die Wartezeit für die Mindest-Wendezeit (3 min) und, bei verschiedenen Endhaltepunkten, eine **Leerfahrt** (25 km/h, derselbe Verbrauch) reicht; höchstens 240 min Wartezeit.
* **Energie:** 1,3 kWh/km, Reserve 10 % von C (nutzbar sind 90 %), jeder Bus startet voll, **Winter** = Verbrauch mal 1,36, also +36 % (Annahme; `ladestrategie-demo` liest den Wintertestwert AAA, 35,6 % bei −6,6 °C, als Mehrverbrauch; ein Effizienzverlust von 35,6 % ergäbe mal 1,55, der Faktor ist also eher niedrig angesetzt; Quelle nur über ein Suchergebnis gesehen). Die Ladeleistung bleibt gleich.
* **Laden:** linear bis C (keine Ladekurve), nur in der Wartezeit nach Abzug von Wendezeit, Leerfahrt und 3 min An- und Abstecken; an beiden Endhaltepunkten oder nur an A. **Ladeplätze:** ein Ladevorgang belegt einen Platz die ganze Wartezeit am Haltepunkt (Annahme).
* **Dieselbus:** keine Energiegrenze. **Gemischte Flotte:** je Kette Diesel oder Elektro, höchstens F Busse insgesamt, möglichst wenige Dieselbusse.
* Formeln: Expander „📐 Mathematische Formulierung“ der App.

## Methodik

* **Dieselumlauf** (Referenz): n minus maximales Matching; Beweis durch eine Knotenüberdeckung gleicher Größe (Satz von König), `verify_diesel_proof` prüft sie ohne Löser.
* **Vier Regeln** (Fahrten in Abfahrtsreihenfolge, unter den möglichen Bussen wählen, sonst neuer Bus): **Spät** (kürzeste Standzeit), **Früh** (längste Standzeit), **Ladestand max.**, **Ladestand min.**; dazu die naheliegende Heuristik **Dieselplan, dann trennen** (ohne Quelle für den Praxiseinsatz) (Dieselumlauf elektrifizieren, Kette trennen, wo die Batterie nicht reicht). Der Gleichstand beim Ladestand ist wählbar (Einsatzreihenfolge, früh, spät).
* **Exakt (CP-SAT):** je Anschluss eine Ja/Nein-Variable, je Fahrt der Ladestand, bei begrenzten Plätzen je Anschluss die Entscheidung „laden“ mit einem Zeitraum und `AddCumulative` je Haltepunkt; Zeitlimit, höchstens 4 Arbeiter, beste Regel als Startlösung. **Ohne Beweis** steht die Zahl als obere Schranke („nicht bewiesen“) mit der bewiesenen unteren Schranke, nie als Optimum. Verbrauch wird auf 0,01 kWh auf-, Ladung abgerundet (die Rundung geht zu Lasten des Modells).
* **Prüfer** (`ebu_energy.check_plan`): rechnet jede Lösung (Regel oder CP-SAT) in Fließkomma nach, einschließlich der Plätze, ohne die Rundung des Lösers und unabhängig von den Löservariablen; er teilt sich mit dem Löser aber die Definitionen von Energie, Laden und Anschlüssen (die Modelldefinition prüft das Aufzählungs-Orakel mit eigener Physik, siehe „Verifikation“). Abgelehnt: 0 von 1.420 Zeilen der Messreihen (jede mit der exakten Lösung; die 240 Zeilen der gemischten Flotte ohne Regeln, die übrigen mit allen Regeln).
* **Monotone Hülle:** Ein Umlauf, der mit weniger Batterie, Ladeleistung, Ladern oder Plätzen oder mehr Verbrauch zulässig ist, ist auch mit mehr zulässig. Die Auswertung setzt die beste bekannte Zahl jeder Zelle auf das Minimum über alle schwächeren Zellen und die untere Schranke auf das Maximum über alle stärkeren. Sie verbesserte in dieser Messreihe die oberen Schranken in 0 Zellen und machte 1 Zelle(n) zusätzlich beweisbar (untere Schranke einer stärkeren Zelle).

## Befunde (gemessen, keine Behauptungen)

Messreihe: Zufalls-Seeds 0 bis 9 (je Zelle zehn Fahrpläne), Zeitlimit 30 s je Rechnung auf dem Entwicklungsrechner (auf anderen Rechnern kann eine Zelle anders ausgehen); „≤“ vor einer Zahl: nicht in allen zehn Fahrplänen bewiesen, dann obere Schranke. Aufschlag = Elektro-Umlauf minus Dieselumlauf, in Bussen, Mittel über die zehn Fahrpläne.

| Frage | Befund | Beleg |
|---|---|---|
| **Wie groß ist der Aufschlag?** | Eine **Rampe über die Batterie**; über die Ladeleistung fällt der Aufschlag schon zwischen 0 und 10 kW stark (das Raster ist dort grob, ob dazwischen ein Sprung liegt, ist nicht gemessen). Sommer, Lader an beiden Endhaltepunkten, C = 60 kWh: ≤ 5,7 ohne Laden (3 von 10 Fahrplänen bewiesen, mittlere bewiesene untere Schranke 4,2), 1,3 bei 10 kW, 0,5 bei 20 kW, 0,3 bei 40 kW (je 10 von 10 bewiesen). Bei C = 120 kWh ist der Aufschlag in allen vier Ladeleistungen 0,0 (10 von 10 bewiesen). | `test_claims.py::test_ramp_*` |
| **Was ändert der Winter?** | Winter, C = 60 kWh, Lader an beiden: ≤ 3,6 bei 10 kW (6 von 10 bewiesen) gegen 1,3 im Sommer; 1,9 bei 20 kW gegen 0,5. Im Raster (Mittel je Zelle, 32 Zellen aus Batterie, Ladeleistung und Ladersetzung) ist der Winter-Aufschlag in 28 Zellen größer als der Sommer-Aufschlag (in 16 von 20 Zellen, in denen beide Jahreszeiten voll bewiesen sind), in 0 kleiner (das folgt aus der Monotonie der Hülle und ist kein Messergebnis). Ohne Laden gilt exakt: **Winter bei C kWh = Sommer bei C/1,36 kWh** (Aufzählung auf 30 Mini-Instanzen, 30 von 30 gleich; nur für P = 0). | `test_claims.py::test_winter_*`, `test_oracle_ebus_umlauf.py::test_winter_*` |
| **Wo endet die Rampe?** | Ohne Laden (P = 0, Lader an beiden, 80 Zeilen): In den 7 Zeilen, in denen die nutzbare Batterie (90 % von C) die Energie der energiereichsten Dieselkette deckt (diese Ketten brauchen 74 bis 102 kWh; über alle Instanzen und beide Jahreszeiten 74 bis 169 kWh), ist der Aufschlag 7 von 7 Mal 0 (bewiesen, der Dieselumlauf selbst ist dann fahrbar). In den 73 übrigen Zeilen liegt die beste bekannte Zahl in 62 über dem Dieselumlauf (61 davon bewiesen positiv); in 11 ist der Aufschlag bewiesen 0, obwohl die Batterie für die Dieselkette nicht reicht. | `test_claims.py::test_chain_energy_*` |
| **Hilft ein zweiter Lader?** | Lader nur am Endhaltepunkt A statt an beiden: in 225 beiderseits bewiesenen Paaren mit Laden (Rampe-Raster ohne die 37 Paare mit P = 0, in denen die Lader gleichgültig sind) mehr Busse in 78, gleich viele in 147 (weniger Busse mit weniger Ladern kann nicht vorkommen, die 0 ist kein Messergebnis); mittlerer Aufschlag 0,8 statt 0,4 Bussen; nur die leichteren, beweisbaren Zellen. | `test_claims.py::test_chargers_*` |
| **Sind die Ladeplätze ein Engpass?** | Bei gleicher Ladeleistung kostet ein Platz je Endhaltepunkt Busse. Mittel über zehn Fahrpläne (Sommer, C = 60 kWh, Lader an beiden Endhaltepunkten), Aufschlag bei 1 / 2 / unbegrenzten Plätzen: 20 kW ≤ 2,1 / 0,6 / 0,5, 40 kW 0,6 / 0,3 / 0,3, 150 kW 0,1 / 0,1 / 0,1; mit Lader nur an A bei 40 kW ≤ 2,5 / 0,8 / 0,7. Bewiesen sind 71 von 120 Zeilen mit einem Platz, 106 von 120 mit zwei und 120 von 120 mit unbegrenzten Plätzen: die Zahlen mit „≤“ sind obere Schranken, der wahre Mittelwert kann niedriger sein. Nur in beiderseits bewiesenen Paaren (ein Platz gegen unbegrenzt, 71 Paare, bevorzugt die leichten Zellen): mehr Busse in 22, gleich viele in 49, weniger in 0; mittlerer Aufschlag 0,6 statt 0,3. Zwei Plätze gegen unbegrenzt: mehr Busse in 9 von 106 Paaren. Bei 150 kW fällt der Platz weniger ins Gewicht, verschwindet aber nicht: ein Platz gegen unbegrenzt, mehr Busse in 8 von 39 bewiesenen Paaren (20 kW: 5 von 8, 40 kW: 9 von 24). | `test_claims.py::test_slots_*` |
| **Wie weit liegen einfache Regeln vom Optimum?** | siehe den Absatz „Regeln“ unter der Tabelle | `test_claims.py::test_rules_*` |
| **Wie viele Dieselbusse bleiben bei fester Flotte?** | Flotte = Dieselmindestflotte (Lader an beiden, unbegrenzte Plätze, Batterie 60, 80 und 100 kWh, P = 0 und 20 kW, Sommer und Winter, 240 Zeilen, 213 bewiesen): im Mittel 2,5 Dieselbusse (alle 120 Zeilen bewiesen); mit einem Bus Reserve ≤ 1,4 (obere Schranke; mittlere untere Schranke 0,9; 93 von 120 Zeilen bewiesen). Mit Reserve 1 sinkt die Zahl der Dieselbusse (beste bekannte Zahlen) in 74 von 120 Paaren. Beispiele (Mittel, Reserve 0): Winter, C = 60, 20 kW: 5,5; Sommer, C = 60, 20 kW: 1,4. | `test_claims.py::test_hybrid_*` |
| **Gilt das auch im Takt-Fahrplan?** | Preset „Gleichmäßiger Takt“ (20 min, Wendezeit mindestens 10 % der Fahrzeit und mindestens 5 min, hier 5 min, 42 Fahrten, Dieselumlauf 4 bis 5 Busse; ein Fahrplan, der Zufalls-Seed verschiebt nur den Versatz): Aufschlag Sommer, C = 60, 10 kW ≤ 2,7 (6 von 10 bewiesen, mittlere untere Schranke 1,9; Generator-Fahrpläne: 1,3), 20 kW ≤ 1,5 (8 von 10 bewiesen; Generator: 0,5). Annahme-Fahrplan, kein echter. | `test_claims.py::test_takt_*` |
| **Wie schnell ist der Beweis?** | Median 0,5 s je exakter Rechnung in dieser Messkonfiguration (3 Arbeiter je Lösung, mehrere Prozesse gleichzeitig; ob eine Zelle im Zeitlimit bewiesen wird, hängt vom Lauf ab) (1.000 Zeilen Rampe und Ladeplätze); 699 von 830 bewiesenen Zeilen in höchstens 1 s, 794 in höchstens 5 s. In der Rampe sind 534 von 640 Zeilen bewiesen; bei 335 Zeilen liegt die obere Schranke über dem Dieselumlauf, davon 229 bewiesen; **ohne Laden und mit kleiner Batterie bleibt der Beweis oft aus** (Sommer, C = 60, 0 kW: 3 von 10 Fahrplänen bewiesen). | `test_claims.py::test_proof_*` |

### Regeln gegen das bewiesene Optimum

**Messreihe, Demo-Größe** (Zufalls-Seeds 0 bis 9, Raster Batterie 60 bis 120 kWh × Ladeleistung 0 bis 40 kW × Sommer/Winter × zwei Ladersetzungen; 229 bewiesene Zeilen mit Aufschlag):

- Die beste der fünf Regeln trifft das bewiesene Optimum in **36 von 229** Zeilen und liegt im Mittel 1,7 Busse darüber (höchstens 5).
- „Dieselplan elektrifizieren, dann trennen“ ist die schlechteste Regel: im Mittel +5,0 Busse, trifft in 0 von 229 Zeilen.
- **Mehr Ressource kann eine Regel verschlechtern.** In den Rastern über 200 Zufalls-Seeds (nur Regeln, 12.800 Zeilen) braucht „Spät“ bei der nächstgrößeren Batterie mehr Busse in 42 von 9.600 benachbarten Zellpaaren und bei der nächsthöheren Ladeleistung in 131 von 9.600; „Ladestand min.“ in 89 bzw. 306, „Ladestand max.“ in 53 bzw. 28, „Früh“ in 89 bzw. 188; „Dieselplan, dann trennen“ in 0 und 0. Das bewiesene Optimum ist in allen 380 (Batterie) bzw. 373 (Leistung) beiderseits bewiesenen Paaren der zehn Zufalls-Seeds monoton (Verletzungen: 0 und 0).
- **Beispiel:** Zufalls-Seed 8, Winter, Lader an beiden Endhaltepunkten, 10 kW: „Spät“ braucht bei 100 kWh 8 Busse, bei 120 kWh 10; das Optimum geht von 8 auf 7 Busse zurück (beides bewiesen). In der App: diese Einstellungen wählen und beide Batteriegrößen vergleichen.
- **Gleichstand beim Ladestand:** Bei „Ladestand max.“ ändert der Gleichstandsbruch (Einsatzreihenfolge, früh, spät) die Busanzahl in 97 von 12.800 Zeilen (0,8 %); „früh“ ist gegenüber der Einsatzreihenfolge in 6 Zeilen besser und in 34 schlechter, „spät“ in 14 besser und in 43 schlechter. In dieser Demo-Größe ist der Effekt klein und kein Ausweg; in anderen Größen nicht gemessen.

### Befunde, die sich gegenüber der Vormessung nicht bestätigt haben

Die Vormessung zu dieser Demo (zwei Linien, Tagesmaßstab, anderer Generator) vermutete zwei Wirkungen (der Gleichstandsbruch kippt die Regel; Regeln werden mit mehr Ladeleistung oft schlechter), die in der Demo-Größe nur schwach wiederkehren: (1) **Der Gleichstandsbruch kippt die Regel kaum:** er ändert die Busanzahl von „Ladestand max.“ nur in 97 von 12.800 Zeilen. (2) **Regeln werden mit mehr Ladeleistung oder Batterie nur selten schlechter** (oben: höchstens 3,2 % der Zellpaare je Regel und Richtung). Beides sind Aussagen über diese Demo-Größe; ob sie im Tagesmaßstab anders ausfallen, ist hier nicht gemessen. Die Vormessung fand im Tagesmaßstab (zwei Linien, rund 200 Fahrten) keinen beweisbaren positiven Aufschlag; mit dem Generator dieser Demo ist der Beweis bei einer Linie und 86 bis 98 Fahrten in 13 von 35 Zeilen mit Aufschlag gelungen, bei 179 bis 200 Fahrten in 1 von 5 (Zeitlimit 30 s).

## Ehrliche Grenzen

- **Demo-Größe: eine Linie, höchstens 50 Fahrten** (der Generator erzeugt hier 38 bis 46). Darüber beweist der exakte Löser nicht mehr alles: Mit demselben Generator über den ganzen Tag (86 bis 98 Fahrten, Dieselumlauf 5 bis 7 Busse, 60 Zeilen, Zeitlimit 30 s) sind 13 von 35 Zeilen mit Aufschlag bewiesen, die größte Lücke zwischen oberer und unterer Schranke beträgt 2 Busse; bei halbem Takt (179 bis 200 Fahrten, 20 Zeilen) sind es 1 von 5 bei einer größten Lücke von 2 Bussen. Ohne Beweis ist die gezeigte Zahl eine obere Schranke, nie ein Optimum.
- **Fahrpläne, Linienlänge, Takte, Geschwindigkeit, Verbrauch (1,3 kWh/km), Reserve (10 % von C) und Winterfaktor (1,36) sind Annahmen des Generators**, keine echten Fahrplan- oder Verbrauchsdaten. Der Winterfaktor ist +36 % Verbrauch; der Wintertestwert, aus dem `ladestrategie-demo` ihn ableitet (AAA, 35,6 % bei −6,6 °C), ist ein Effizienzverlust und ergäbe als Mehrverbrauch gelesen 1,55: der Faktor ist eher niedrig angesetzt (Quelle nur über ein Suchergebnis gesehen).
- **Batteriegrößen gelten für diesen Sieben-Stunden-Ausschnitt.** Die energiereichste Dieselkette braucht 74 bis 169 kWh (Sommer und Winter zusammen); die Rampe endet in dieser Größenordnung. Die kWh-Zahlen nicht auf Busse mit Tagesumlauf übertragen.
- **Lineares Laden bis C** (keine Ladekurve): überschätzt das Laden bei hohem Ladestand.
- **Ein Ladevorgang belegt den Platz die ganze Wartezeit** am Endhaltepunkt: überschätzt die Belegung gegenüber kurzen realen Ladevorgängen und damit den Ladeplatz-Engpass.
- **Keine Aus- und Einsetzfahrten, kein Nachtladen im Depot, keine Heizung als eigener Verbraucher** (der Winter ist ein Faktor auf den Verbrauch), **keine Streuung der Fahrzeiten**, nur eine Linie mit zwei Endhaltepunkten.
- **Der „Gleichmäßige Takt“** (20 min je Richtung, Wendezeit mindestens 10 % der Fahrzeit und mindestens 5 min) ist ein Annahme-Fahrplan; für die 10-%-Regel wurde keine Quelle gelesen.
- **Zehn Zufalls-Seeds je Zelle** (Fahrplan-Generator), deskriptive Mittel ohne Test auf Signifikanz; das Zeitlimit von 30 s gilt für den Entwicklungsrechner.

## Verifikation

168 Tests (`python -m pytest tests/ -n 8`), zusammengesetzt aus:

* **Orakel** (`tests/test_oracle_ebus_umlauf.py`): der exakte Löser gegen die **vollständige Aufzählung** aller Zerlegungen in Ketten mit eigener, neu geschriebener Physik (Mini-Instanzen bis 7 Fahrten, zwei Familien: Zufall und Takt; mit und ohne Platzgrenze, mit Teilmengen-Aufzählung der Ladeentscheidungen) und die gemischte Flotte gegen Aufzählung; Dieselbasis gegen networkx (Hopcroft-Karp) und gegen Aufzählung; Monotonie des bewiesenen Optimums; der Prüfer lehnt von Hand gebaute unzulässige Pläne ab. **Großer Lauf (Scratch, `tools/oracle_scratch.py`):** 878 Mini-Instanzen für den Elektro-Umlauf und 600 Fälle der gemischten Flotte verglichen, 0 Abweichungen; die Ladeplatzgrenze ändert das Optimum in 10 dieser Fälle (nur dort prüft die Aufzählung sie wirklich).
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
