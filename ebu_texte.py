"""Texte aus der Messreihe (data/messreihe.json): Beschriftungen unter den Tabellen, Befunde zu den Regeln und die Grenzen.

Dieselben Texte stehen in der README (tests/test_claims.py prüft, dass die README sie enthält): eine Quelle, keine zwei von Hand synchron gehaltenen Fassungen.
Jede Zahl kommt aus dem Wörterbuch `d` (von tools/messreihe_auswertung.py erzeugt), nie aus dem Quelltext."""

import ebu_constants as C


def f1(x) -> str:
    return f"{x:.1f}".replace(".", ",")


def num(x: int) -> str:
    """Ganze Zahl mit Tausenderpunkt (nur die Zahl, nie ein ganzer Satz umformatieren)."""
    return f"{x:,}".replace(",", ".")


def pct(k, n) -> str:
    return f"{100.0 * k / n:.1f}".replace(".", ",") + " %"


def rampe_caption(d: dict) -> str:
    m = d["meta"]["rampe"]
    return (f"Zelle: mittlerer Aufschlag der besten bekannten Zahl gegen den Dieselumlauf (Dieselumlauf im Mittel {f1(m['diesel_mean'])} Busse, {m['n_min']} bis {m['n_max']} Fahrten); "
            f"„≤“ = nicht in allen 10 Zufalls-Seeds bewiesen, dann obere Schranke. Zeitlimit {d['meta']['time_limit']:.0f} s je Rechnung auf dem Entwicklungsrechner; "
            "auf anderen Rechnern kann eine Zelle anders ausgehen. Lader und Jahreszeit folgen der Seitenleiste.")


def plaetze_caption(d: dict) -> str:
    return "Mittlerer Aufschlag der besten bekannten Zahl, zehn Zufalls-Seeds je Zeile; „≤“ = nicht in allen 10 Seeds bewiesen. Der Platz belegt die ganze Wartezeit (Annahme)."


def gemischt_caption(d: dict) -> str:
    return "Reserve 0: Flotte = Dieselmindestflotte. „≤“ = nicht in allen 10 Zufalls-Seeds bewiesen. Mittelwerte über 10 Fahrpläne, keine Aussage über einen einzelnen."


def regeln_markdown(d: dict) -> str:
    r = d["regeln"]
    b, big = r["best_of"], r["grosse_reihe"]
    pr = r["per_rule"]
    bn = big["nonmono"]
    ex = big["examples_in_sweep"]["spaet|c"]
    lines = [
        f"**Messreihe, Demo-Größe** (Zufalls-Seeds 0 bis 9, Raster Batterie 60 bis 120 kWh × Ladeleistung 0 bis 40 kW × Sommer/Winter × zwei Ladersetzungen; "
        f"{r['positive_proven']} bewiesene Zeilen mit Aufschlag):",
        "",
        f"- Die beste der fünf Regeln trifft das bewiesene Optimum in **{b['hits']} von {b['of']}** Zeilen und liegt im Mittel {f1(b['mean_extra'])} Busse darüber (höchstens {b['max_extra']}).",
        f"- „Dieselplan elektrifizieren, dann trennen“ ist die schlechteste Regel: im Mittel +{f1(pr['diesel_trennen']['mean_extra'])} Busse, trifft in {pr['diesel_trennen']['hits']} von {pr['diesel_trennen']['of']} Zeilen.",
        f"- **Mehr Ressource kann eine Regel verschlechtern.** In den Rastern über 200 Zufalls-Seeds (nur Regeln, {num(big['rows'])} Zeilen) braucht „Spät“ bei der nächstgrößeren Batterie mehr Busse in "
        f"{bn['spaet']['c'][0]} von {num(bn['spaet']['c'][1])} benachbarten Zellpaaren und bei der nächsthöheren Ladeleistung in {bn['spaet']['p'][0]} von {num(bn['spaet']['p'][1])}; „Ladestand min.“ in "
        f"{bn['soc_min']['c'][0]} bzw. {bn['soc_min']['p'][0]}, „Ladestand max.“ in {bn['soc_max']['c'][0]} bzw. {bn['soc_max']['p'][0]}, „Früh“ in {bn['frueh']['c'][0]} bzw. {bn['frueh']['p'][0]}; "
        f"„Dieselplan, dann trennen“ in {bn['diesel_trennen']['c'][0]} und {bn['diesel_trennen']['p'][0]}. Das bewiesene Optimum ist in allen {r['opt_monotone']['c'][1]} (Batterie) bzw. "
        f"{r['opt_monotone']['p'][1]} (Leistung) beiderseits bewiesenen Paaren der zehn Zufalls-Seeds monoton (Verletzungen: {r['opt_monotone']['c'][0]} und {r['opt_monotone']['p'][0]}).",
        f"- **Beispiel:** Zufalls-Seed {ex['seed']}, {ex['season']}, Lader an beiden Endhaltepunkten, {ex['p_from']} kW: „Spät“ braucht bei {ex['c_from']} kWh "
        f"{ex['buses_from']} Busse, bei {ex['c_to']} kWh {ex['buses_to']}; das Optimum geht von {ex['opt_from']} auf {ex['opt_to']} Busse zurück "
        "(beides bewiesen). In der App: diese Einstellungen wählen und beide Batteriegrößen vergleichen.",
        f"- **Gleichstand beim Ladestand:** Bei „Ladestand max.“ ändert der Gleichstandsbruch (Einsatzreihenfolge, früh, spät) die Busanzahl in {big['tie_differ']} von {num(big['tie_rows'])} Zeilen "
        f"({pct(big['tie_differ'], big['tie_rows'])}); „früh“ ist gegenüber der Einsatzreihenfolge in {big['tie_better']['frueh']} Zeilen besser und in {big['tie_better']['frueh_worse']} schlechter, "
        f"„spät“ in {big['tie_better']['spaet']} besser und in {big['tie_better']['spaet_worse']} schlechter. In dieser Demo-Größe ist der Effekt klein und kein Ausweg; in anderen Größen nicht gemessen.",
    ]
    return "\n".join(lines)


def grenzen_markdown(d: dict) -> str:
    t, t2, rm = d["tag"], d["tag2"], d["meta"]["rampe"]
    f = d["fakten"]["kettenenergie"]
    lines = [
        f"- **Demo-Größe: eine Linie, höchstens {C.MAX_TRIPS} Fahrten** (der Generator erzeugt hier {rm['n_min']} bis {rm['n_max']}). Darüber beweist der exakte Löser nicht mehr alles: "
        f"Mit demselben Generator über den ganzen Tag ({t['n_min']} bis {t['n_max']} Fahrten, Dieselumlauf {t['diesel_min']} bis {t['diesel_max']} Busse, {t['rows']} Zeilen, "
        f"Zeitlimit {t['time_limit']:.0f} s) sind {t['positive_proven']} von {t['positive']} Zeilen mit Aufschlag bewiesen, die größte Lücke zwischen oberer und unterer Schranke beträgt {t['gap_max']} Busse; "
        f"bei halbem Takt ({t2['n_min']} bis {t2['n_max']} Fahrten, {t2['rows']} Zeilen) sind es {t2['positive_proven']} von {t2['positive']} bei einer größten Lücke von {t2['gap_max']} Bussen. "
        "Ohne Beweis ist die gezeigte Zahl eine obere Schranke, nie ein Optimum.",
        "- **Fahrpläne, Linienlänge, Takte, Geschwindigkeit, Verbrauch (1,3 kWh/km), Reserve (10 % von C) und Winterfaktor (1,36) sind Annahmen des Generators**, keine echten Fahrplan- oder Verbrauchsdaten. Der Winterfaktor ist +36 % Verbrauch; der Wintertestwert, aus dem `ladestrategie-demo` ihn ableitet (AAA, 35,6 % bei −6,6 °C), ist ein Effizienzverlust und ergäbe als Mehrverbrauch gelesen 1,55: der Faktor ist eher niedrig angesetzt (Quelle nur über ein Suchergebnis gesehen).",
        f"- **Batteriegrößen gelten für diesen Sieben-Stunden-Ausschnitt.** Die energiereichste Dieselkette braucht {f['chain_kwh_min']:.0f} bis {f['chain_kwh_max']:.0f} kWh (Sommer und Winter zusammen); "
        "die Rampe endet in dieser Größenordnung. Die kWh-Zahlen nicht auf Busse mit Tagesumlauf übertragen.",
        "- **Lineares Laden bis C** (keine Ladekurve): überschätzt das Laden bei hohem Ladestand.",
        "- **Ein Ladevorgang belegt den Platz die ganze Wartezeit** am Endhaltepunkt: überschätzt die Belegung gegenüber kurzen realen Ladevorgängen und damit den Ladeplatz-Engpass.",
        "- **Keine Aus- und Einsetzfahrten, kein Nachtladen im Depot, keine Heizung als eigener Verbraucher** (der Winter ist ein Faktor auf den Verbrauch), **keine Streuung der Fahrzeiten**, nur eine Linie mit zwei Endhaltepunkten.",
        "- **Der „Gleichmäßige Takt“** (20 min je Richtung, Wendezeit mindestens 10 % der Fahrzeit und mindestens 5 min) ist ein Annahme-Fahrplan; für die 10-%-Regel wurde keine Quelle gelesen.",
        f"- **Zehn Zufalls-Seeds je Zelle** (Fahrplan-Generator), deskriptive Mittel ohne Test auf Signifikanz; das Zeitlimit von {d['meta']['time_limit']:.0f} s gilt für den Entwicklungsrechner.",
    ]
    return "\n".join(lines)
