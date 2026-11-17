"""Elektrobus-Umlauf: Wie viele Busse braucht das Laden? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Eine Linie, höchstens 50 Fahrten (Demo-Größe, damit der exakte Löser die Aufschläge in Sekunden beweist). Aufbau und Regeln: DEMO-PLAYBOOK.md (§2).

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import ebu_constants as C
import ebu_diesel as DS
import ebu_energy as E
import ebu_evaluation as ev
import ebu_rules as R
import ebu_texte as T
import ebu_layout as LAY
import ebu_presets as PS
import ebu_scenario as SC
import ebu_visualization as V
import modul_frisch

modul_frisch.aktualisieren(__file__)      # geänderte Hilfsmodule nach einem Update neu laden (Cloud behält sie sonst bis zum Neustart)

st.set_page_config(page_title="Elektrobus-Umlauf – Sebastian Hanisch", layout="wide")

TIMETABLE_LABELS = {"zufall": "Generator mit Spitze (Zufalls-Seed)", "takt": "Gleichmäßiger Takt (Wendezeit-Regel)"}
CHARGER_LABELS = {"beide": "An beiden Endhaltepunkten", "nur A": "Nur am Endhaltepunkt A"}
CHARGER_SENTENCE = {"beide": "Lader an beiden Endhaltepunkten", "nur A": "Lader nur am Endhaltepunkt A"}


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return ev.analyse(settings)


@st.cache_data(show_spinner=False)
def _exact(settings, limit):
    return ev.solve_exact(settings, ev.analyse(settings), limit)


@st.cache_data(show_spinner=False)
def _ramp(settings, limit):
    return ev.ramp_live(settings, ev.analyse(settings), time_limit=limit)


@st.cache_data(show_spinner=False)
def _slots(settings, limit):
    return ev.slots_live(settings, ev.analyse(settings), time_limit=limit)


@st.cache_data(show_spinner=False)
def _hybrid(settings, limit):
    return ev.solve_hybrid(settings, ev.analyse(settings), limit)


@st.cache_data(show_spinner=False)
def _messreihe():
    return ev.load_messreihe()


def _fmt_slots(v):
    return "unbegrenzt" if v == C.SLOTS_UNLIMITED else str(v)


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in ebu_layout.py).
st.html(LAY.kopf_css(LAY.dunkles_design()))
with st.container(key="kopf"):
    st.title("🚌 Elektrobus-Umlauf: Wie viele Busse braucht das Laden?")
st.markdown(
    f"""
Ein Dieselbus fährt, bis der Fahrplan zu Ende ist. Ein **Elektrobus** hat eine Batteriegrenze, lädt in den Wendezeiten an den Endhaltepunkten und braucht dafür
oft **mehr Busse** als der Dieselumlauf. Diese Demo rechnet **eine Linie mit höchstens {C.MAX_TRIPS} Fahrten** (bewusst Demo-Größe: dort beweist der exakte Löser die meisten Zellen in
Sekunden, wie viele Busse nötig sind; ohne Laden und mit kleiner Batterie bleibt der Beweis oft aus). Sie beantwortet vier Fragen: **wie groß der Aufschlag** je Batterie und Ladeleistung ist, ob die **Ladeplätze am Endhaltepunkt**
ein verdeckter Engpass sind, wie weit **einfache Regeln** vom bewiesenen Optimum entfernt liegen und **wie viele Dieselbusse** bei fester Flottengröße bleiben.
Fahrpläne, Verbrauch und Winterfaktor sind **Annahmen des Generators**, keine echten Daten (Expander „🚧 Wo die Annahmen enden“).

Wer die Frage zuerst ohne Fachbegriffe verstehen will, öffnet „💬 In einfachen Worten“. Weiter unten: vier **Kernfragen**, dann die Expander **🔧 Wie wir das erreichen – vollständiger Methodenvergleich**, **🚧 Wo die Annahmen enden** und **📐 Mathematische Formulierung**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/elektrobus-umlauf-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Eine Buslinie hat einen Fahrplan mit vielen Fahrten. Ein Umlauf ordnet jede Fahrt einem Bus zu, gesucht ist die kleinste Zahl von Bussen. Ein Dieselbus fährt, bis der Fahrplan zu Ende ist. Ein Elektrobus hat eine Batterie, die für lange Ketten von Fahrten nicht reicht: Er lädt in den Wendezeiten an den Endhaltepunkten, oder ein zweiter Bus übernimmt. Die Demo fragt, wie viele Busse das zusätzlich kostet, was es ausmacht, wenn nur ein Bus gleichzeitig laden darf, und wie weit einfache Regeln vom bewiesenen Optimum entfernt liegen. Gerechnet wird eine Linie mit höchstens 50 Fahrten. Fahrpläne, Verbrauch und Winterfaktor erfindet ein Generator, es sind keine echten Daten.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/elektrobus-umlauf-erklaert.html)
        """
    )
# erklaerseite:einfach:end

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

PS.load_permalink_settings()
PS.init_session_state_defaults()

with st.sidebar:
    PS.sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("🔋 Bus")
    c = st.slider("Batterie C (kWh)", *PS.bounds("c_slider"), step=C.C_STEP, key="c_slider",
                  help="Nutzbar sind 90 % von C (10 % Reserve). Der Bus startet voll. Die Zahlen gelten für diesen 7-Stunden-Ausschnitt, nicht für einen ganzen Tag.")
    season = st.radio("Jahreszeit", C.SEASON_OPTIONS, key="season_radio", horizontal=True,
                      help=f"Winter: Verbrauch × {str(C.WINTER_FACTOR).replace('.', ',')} (Annahme, aus dem Wintertestwert in der Demo zur Ladestrategie abgeleitet). Die Ladeleistung bleibt gleich.".replace(".", ","))
    st.header("⚡ Laden")
    p = st.slider("Ladeleistung P (kW)", *PS.bounds("p_slider"), step=C.P_STEP, key="p_slider",
                  help="Lineares Laden bis C (keine Ladekurve). Geladen wird nur in der Wartezeit zwischen zwei Fahrten, nach Abzug von Wendezeit, Leerfahrt und 3 min An- und Abstecken. 0 = kein Laden.")
    chargers = st.radio("Lader", C.CHARGER_OPTIONS, key="chargers_radio", format_func=CHARGER_LABELS.get,
                        help="Ein Lader am Endhaltepunkt A ist zugleich der Ladeort für Fahrten, die dort ankommen oder (nach einer Leerfahrt) dort abfahren.")
    slots = st.select_slider("Ladeplätze je Endhaltepunkt", C.SLOT_OPTIONS, key="slots_select", format_func=_fmt_slots,
                             help="Wie viele Busse gleichzeitig laden dürfen. Ein Ladevorgang belegt den Platz die ganze Wartezeit am Endhaltepunkt (Annahme).")
    st.header("🚌 Flotte")
    reserve = st.slider("Flotte = Dieselmindestflotte + …", *PS.bounds("reserve_slider"), step=1, key="reserve_slider",
                        help="Nur für die gemischte Flotte (Kernfrage 4): Gesamtzahl der Busse = Dieselmindestflotte plus diese Reserve; gefragt ist, wie viele davon Diesel bleiben müssen.")
    st.header("🚏 Fahrplan")
    timetable = st.radio("Fahrplan", C.TIMETABLES, key="timetable_radio", format_func=TIMETABLE_LABELS.get,
                         help="Der Generator zieht Länge, Geschwindigkeit, Takte und Versatz aus dem Zufalls-Seed. Der gleichmäßige Takt hat eine feste Linie, einen Takt von 20 min je Richtung "
                              "und eine Wendezeit von mindestens 10 % der Fahrzeit und mindestens 5 min (hier 5 min bei 32 min Fahrzeit; Annahme); der Zufalls-Seed verschiebt nur den Versatz der Gegenrichtung.")
    seed = st.number_input("Zufalls-Seed", *PS.bounds("seed_input"), key="seed_input", step=1)
    st.button("🎲 Neuen Fahrplan würfeln", width="stretch", on_click=PS.randomize_seed)

PS.sync_query_params({"seed_input": int(seed), "timetable_radio": timetable, "c_slider": int(c), "season_radio": season, "p_slider": int(p),
                   "chargers_radio": chargers, "slots_select": int(slots), "reserve_slider": int(reserve)})

settings = ev.Settings(**PS.current_settings_dict())
a = _analysis(settings)
inst, prm, D = a.inst, a.prm, a.diesel
usable = prm.c - prm.reserve

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ergebnis")
limit = C.EXACT_TIME_LIMIT_S
with st.spinner(f"Exakte Rechnung (CP-SAT), Zeitlimit {limit:.0f} Sekunden …"):
    res = _exact(settings, limit)
lo, hi = ev.surcharge_bounds(D.buses, res)
best_name, best_plan = a.best if a.best else (None, None)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Dieselumlauf", f"{D.buses} Busse", delta="bewiesen (König)", delta_color="off",
          help=f"n − Matching: {inst.n} Fahrten, kleinste Zahl von Bussen ohne Batteriegrenze; der Beweis ist eine Knotenüberdeckung gleicher Größe.")
if res.value is None:
    m2.metric("Elektro-Umlauf", "keine Lösung", delta=res.status, delta_color="off")
else:
    label = "Elektro-Umlauf (bewiesen)" if res.proven else "Elektro-Umlauf (obere Schranke)"
    # Delta = mein Wert minus Referenz; die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
    m2.metric(label, f"{res.value} Busse", delta=f"{res.value - D.buses:+d} gegen Diesel", delta_color="inverse" if res.value != D.buses else "off")
if best_plan is None:
    m3.metric("Beste einfache Regel", "keine Lösung", delta_color="off")
elif res.value is None:
    m3.metric("Beste einfache Regel", f"{best_plan.buses} Busse", delta=R.RULE_LABELS[best_name], delta_color="off")
else:
    m3.metric("Beste einfache Regel", f"{best_plan.buses} Busse", delta=f"{best_plan.buses - res.value:+d} gegen Elektro-Umlauf",
              delta_color="inverse" if best_plan.buses != res.value else "off",
              help=f"Regel: {R.RULE_LABELS[best_name]}.")
m4.metric("Nutzbare Batterie", f"{usable:.0f} kWh", delta=f"Dieselkette braucht bis {a.diesel_chain_kwh:.0f} kWh", delta_color="off",
          help="Energie der energiereichsten Kette des Dieselumlaufs (Fahrten plus Leerfahrten, ohne Laden). Reicht die nutzbare Batterie dafür, ist der Dieselumlauf selbst "
               "elektrisch fahrbar und der Aufschlag null; darunter kann er null sein, muss es aber nicht.")

kind, text = ev.verdict_surcharge(D.buses, res)
getattr(st, kind)(text)
if res.plan is not None:
    ok, why = E.check_plan(inst, prm, res.plan)
    st.caption(f"Rechenzeit {T.f1(res.seconds)} s, Status {res.status}. Die Lösung wurde von einem unabhängigen Fließkomma-Prüfer {'angenommen' if ok else 'ABGELEHNT: ' + why}.")
else:
    st.caption(f"Rechenzeit {T.f1(res.seconds)} s, Status {res.status}.")

views = {}
if res.plan is not None:
    views["Elektro-Umlauf (exakt)" + ("" if res.proven else ", nicht bewiesen")] = (res.plan, "Elektro-Umlauf (CP-SAT)")
views["Dieselumlauf (ohne Batteriegrenze)"] = (E.Plan(D.chains, frozenset(), frozenset(range(len(D.chains)))), "Dieselumlauf")
for name, plan in a.plans.items():
    if plan is not None:
        views[f"Regel: {R.RULE_LABELS[name]}"] = (plan, R.RULE_LABELS[name])
choice = st.selectbox("Umlauf anzeigen", list(views), key="view_plan")
plan, ttl = views[choice]
st.plotly_chart(V.build_umlauf(inst, prm, plan, f"{ttl}: {plan.buses} Busse" + (f", davon {plan.diesel_buses} Diesel" if plan.diesel_buses else "")),
                width="stretch", key="main_chart")
st.caption(
    f"Eine Zeile je Bus, Fahrtbalken nach Ladestand bei Ankunft gefärbt (rot = nahe der Reserve von {prm.reserve:.0f} kWh), grün = Ladeplatz belegt, grau = Leerfahrt zwischen den "
    f"Endhaltepunkten. Fahrplan: {inst.n} Fahrten zwischen {SC.fmt_time(min(inst.start))} und {SC.fmt_time(max(inst.end))}, Strecke {T.f1(inst.dist[0])} km, Wendezeit mindestens {inst.layover} min."
)

st.markdown("---")

# --- Kernfragen ----------------------------------------------------------------------------------------------------------------------------

mess = _messreihe()


def _cell_text(cell):
    if cell is None:
        return ""
    prefix = "" if cell["proven"] == cell["n"] else "≤ "
    return f"{prefix}{cell['ub_mean']:.1f}".replace(".", ",") + f"<br>({cell['proven']}/{cell['n']} bewiesen)"


def _ramp_from_messreihe(table):
    xs, ys = list(C.RAMP_P), list(C.RAMP_C)
    z = [[None if table.get(f"{cc}|{pp}") is None else table[f"{cc}|{pp}"]["ub_mean"] for pp in xs] for cc in ys]
    texts = [[_cell_text(table.get(f"{cc}|{pp}")) for pp in xs] for cc in ys]
    return z, xs, ys, texts


st.markdown("## ❓ Kernfrage 1: Wie groß ist der Aufschlag je Batterie und Ladeleistung?")
st.markdown(
    "Der **Aufschlag** ist der Elektro-Umlauf minus der Dieselumlauf, in Bussen. Er fällt über die Batterie stufenweise (eine **Rampe**); über die Ladeleistung fällt er schon zwischen 0 und 10 kW stark, dort ist das Raster der Messreihe grob. Unten: die Rampe für "
    "**diesen Fahrplan** (live, Zeitlimit je Zelle sichtbar) und die vorgerechnete Messreihe über zehn Zufalls-Seeds."
)
ramp_key = (settings.seed, settings.timetable, settings.season, settings.chargers, settings.slots)
cells = len(C.RAMP_C) * len(C.RAMP_P)
if st.button(f"Rampe für diesen Fahrplan rechnen ({cells} exakte Rechnungen)", key="ramp_start",
             help=f"Bis zu {cells * C.RAMP_TIME_LIMIT_S:.0f} Sekunden, meist deutlich weniger: Zellen ohne Beweis laufen bis zum Zeitlimit von {C.RAMP_TIME_LIMIT_S:.0f} s."):
    st.session_state["ramp_done"] = ramp_key
if st.session_state.get("ramp_done") == ramp_key:
    with st.spinner(f"Rechne {cells} Zellen, jede höchstens {C.RAMP_TIME_LIMIT_S:.0f} Sekunden …"):
        ramp = _ramp(settings, C.RAMP_TIME_LIMIT_S)
    z = [[None if ramp[(cc, pp)].value is None else ramp[(cc, pp)].value - D.buses for pp in C.RAMP_P] for cc in C.RAMP_C]
    texts = [[("–" if ramp[(cc, pp)].value is None else ("" if ramp[(cc, pp)].proven else "≤ ") + str(ramp[(cc, pp)].value - D.buses)) for pp in C.RAMP_P] for cc in C.RAMP_C]
    st.plotly_chart(V.build_heatmap(z, C.RAMP_P, C.RAMP_C, texts, "Ladeleistung (kW)", "Batterie (kWh)",
                                  f"Aufschlag in Bussen auf diesem Fahrplan ({season}, {CHARGER_SENTENCE[chargers]}, Plätze {_fmt_slots(slots)}; „≤“ = nicht bewiesen, obere Schranke)"),
                    width="stretch", key="ramp_live_chart")
    n_unproven = sum(1 for r in ramp.values() if not r.proven)
    st.caption(f"{cells - n_unproven} von {cells} Zellen bewiesen; Dieselumlauf: {D.buses} Busse. „–“: keine Lösung im Zeitlimit oder Fahrt allein nicht fahrbar.")
if mess is not None:
    table = mess["rampe"].get(f"{season}|{chargers}")
    if table:
        z, xs, ys, texts = _ramp_from_messreihe(table)
        st.plotly_chart(V.build_heatmap(z, xs, ys, texts, "Ladeleistung (kW)", "Batterie (kWh)",
                                      f"Messreihe: mittlerer Aufschlag in Bussen, Zufalls-Seeds 0 bis 9 ({season}, {CHARGER_SENTENCE[chargers]}, Plätze unbegrenzt)"),
                        width="stretch", key="ramp_mess_chart")
        st.caption(T.rampe_caption(mess))
else:
    st.warning("Die vorgerechnete Messreihe (data/messreihe.json) fehlt.")

st.markdown("## ❓ Kernfrage 2: Sind die Ladeplätze am Endhaltepunkt ein verdeckter Engpass?")
st.markdown(
    "Dieselbe Ladeleistung, aber nur **ein Platz** je Endhaltepunkt: Dann kann nicht jeder Bus in seiner Wendezeit laden. Die Rechnung vergleicht 1, 2 und unbegrenzt viele Plätze "
    "bei den übrigen Einstellungen aus der Seitenleiste (der Regler „Ladeplätze“ wird dabei überschrieben). **Annahme:** ein Ladevorgang belegt den Platz die ganze Wartezeit."
)
slot_key = (settings.seed, settings.timetable, settings.season, settings.c, settings.p, settings.chargers)
if prm.p <= 0:
    st.info("Ohne Ladeleistung (P = 0) wird nicht geladen, also gibt es keinen Ladeplatz-Engpass: Ladeleistung in der Seitenleiste erhöhen.")
else:
    if st.button("Ladeplätze vergleichen (3 exakte Rechnungen)", key="slots_start",
                 help=f"Bis zu {3 * C.RAMP_TIME_LIMIT_S:.0f} Sekunden: jede Rechnung höchstens {C.RAMP_TIME_LIMIT_S:.0f} s."):
        st.session_state["slots_done"] = slot_key
    if st.session_state.get("slots_done") == slot_key:
        with st.spinner(f"Rechne 3 Fälle, jeder höchstens {C.RAMP_TIME_LIMIT_S:.0f} Sekunden …"):
            sres = _slots(settings, C.RAMP_TIME_LIMIT_S)
        rows = []
        for sl, r in sres.items():
            if r.value is None:
                rows.append({"Ladeplätze": _fmt_slots(sl), "Busse": "–", "Aufschlag": "–", "Status": r.status})
            else:
                rows.append({"Ladeplätze": _fmt_slots(sl), "Busse": ("" if r.proven else "≤ ") + str(r.value), "Aufschlag": ("" if r.proven else "≤ ") + str(r.value - D.buses),
                             "Status": "bewiesen" if r.proven else f"nicht bewiesen (mindestens {r.bound})"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        kind, text = ev.verdict_slots(sres, D.buses)
        getattr(st, kind)(text)
if mess is not None and mess.get("plaetze"):
    st.markdown("**Messreihe** (zehn Zufalls-Seeds, mittlerer Aufschlag in Bussen; „≤“ = nicht in allen Seeds bewiesen):")
    prow = []
    for key, cell in mess["plaetze"].items():
        s_, c_, p_, ch_ = key.split("|")
        row = {"Jahreszeit": s_, "Batterie (kWh)": int(c_), "Ladeleistung (kW)": int(p_), "Lader": CHARGER_LABELS[ch_]}
        for sl in ("1", "2", str(C.SLOTS_UNLIMITED)):
            row[f"Plätze {_fmt_slots(int(sl))}"] = _cell_text(cell[sl]).replace("<br>", " ")
        prow.append(row)
    st.dataframe(pd.DataFrame(prow), hide_index=True, width="stretch")
    st.caption(T.plaetze_caption(mess))

st.markdown("## ❓ Kernfrage 3: Wie weit liegen einfache Regeln vom bewiesenen Optimum?")
st.markdown(
    "Fünf Regeln verteilen die Fahrten in Abfahrtsreihenfolge (Erklärung im Expander „🔧 Wie wir das erreichen“). Die Tabelle zeigt sie auf **diesem** Fahrplan gegen das exakte "
    "Ergebnis oben; darunter die Messreihe über viele Fahrpläne und Einstellungen."
)
ref = res.value
rule_rows = []
for name in (*R.RULES, "diesel_trennen"):
    pl = a.plans[name]
    rule_rows.append({"Regel": R.RULE_LABELS[name], "Busse": "keine Lösung" if pl is None else pl.buses,
                      "Mehr als Elektro-Umlauf": "–" if pl is None or ref is None else f"{pl.buses - ref:+d}",
                      "Prüfer": "–" if pl is None else ("angenommen" if a.plans_ok[name] else "ABGELEHNT")})
st.dataframe(pd.DataFrame(rule_rows), hide_index=True, width="stretch")
st.plotly_chart(V.build_rules([r["Regel"] for r in rule_rows], [None if a.plans[n] is None else a.plans[n].buses for n in (*R.RULES, "diesel_trennen")], ref, res.proven, D.buses),
                width="stretch", key="rules_chart")
kind, text = ev.verdict_rules(best_name, best_plan, res)
getattr(st, kind)(text)
_tie = {t: ("keine Lösung" if a.ties[t] is None else f"{a.ties[t]} Busse") for t in R.TIES}
st.markdown(
    f"**Gleichstand zählt:** bei der Regel „Ladestand max.“ entscheidet bei gleichem Ladestand (etwa wenn alle Busse voll sind) sonst nur die Einsatzreihenfolge. Auf diesem Fahrplan "
    f"braucht sie mit Einsatzreihenfolge **{_tie['liste']}**, mit Gleichstand „früh“ (längste Standzeit) **{_tie['frueh']}** und mit Gleichstand „spät“ (kürzeste Standzeit) **{_tie['spaet']}**."
)
if mess is not None:
    st.markdown(T.regeln_markdown(mess))

st.markdown("## ❓ Kernfrage 4: Wie viele Dieselbusse bleiben bei fester Flottengröße?")
fleet = D.buses + settings.reserve_buses
st.markdown(
    f"Die Gesamtflotte darf nicht wachsen: höchstens **{fleet} Busse** (Dieselmindestflotte {D.buses} + Reserve {settings.reserve_buses}, Regler „Flotte“). Gefragt ist, wie viele davon "
    "Dieselbusse bleiben müssen, weil die Batterie für ihre Fahrten nicht reicht. Die Rechnung berücksichtigt die Ladeplätze aus der Seitenleiste (die Messreihe darunter rechnet mit unbegrenzten Plätzen)."
)
hyb_key = (settings.seed, settings.timetable, settings.season, settings.c, settings.p, settings.chargers, settings.slots, settings.reserve_buses)
if st.button("Gemischte Flotte rechnen", key="hybrid_start", help="Eine exakte Rechnung, Zeitlimit 10 Sekunden."):
    st.session_state["hybrid_done"] = hyb_key
if st.session_state.get("hybrid_done") == hyb_key:
    with st.spinner("Rechne die gemischte Flotte (Zeitlimit 10 Sekunden) …"):
        hres = _hybrid(settings, 10.0)
    kind, text = ev.verdict_hybrid(D.buses, fleet, hres)
    getattr(st, kind)(text)
    if hres.plan is not None:
        ok, why = E.check_plan(inst, prm, hres.plan)
        st.caption(f"Rechenzeit {T.f1(hres.seconds)} s; Prüfer: {'angenommen' if ok else 'ABGELEHNT: ' + why}.")
        st.plotly_chart(V.build_umlauf(inst, prm, hres.plan,
                                     f"Gemischte Flotte: {hres.plan.buses} Busse, davon {hres.plan.diesel_buses} Diesel (braun)"), width="stretch", key="hybrid_chart")
if mess is not None and mess.get("gemischt"):
    st.markdown("**Messreihe** (zehn Zufalls-Seeds, Lader an beiden Endhaltepunkten, unbegrenzte Plätze; mittlere Zahl der Dieselbusse bei Flotte = Dieselmindestflotte + Reserve):")
    hrows = []
    for key, cell in mess["gemischt"].items():
        s_, c_, p_, rb_ = key.split("|")
        hrows.append({"Jahreszeit": s_, "Batterie (kWh)": int(c_), "Ladeleistung (kW)": int(p_), "Reserve": int(rb_),
                      "Dieselbusse (Mittel)": ("" if cell["proven"] == cell["n"] else "≤ ") + f"{cell['mean']:.1f}".replace(".", ","),
                      "bewiesen": f"{cell['proven']}/{cell['n']}"})
    st.dataframe(pd.DataFrame(hrows), hide_index=True, width="stretch")
    st.caption(T.gemischt_caption(mess))

st.markdown("---")

# --- Methodenvergleich ---------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_rules, tab_exact, tab_base = st.tabs(["Regeln", "🧮 Exakt (CP-SAT)", "Dieselbasis"])
    with tab_rules:
        st.markdown("Jede Regel verteilt die Fahrten in Abfahrtsreihenfolge und wählt unter den Bussen, die die Fahrt noch fahren können; gibt es keinen, kommt ein neuer, voller Bus.")
        expl = [
            {"Verfahren": "Spät", "Idee": "Der Bus mit der kürzesten Standzeit fährt weiter (er hat am wenigsten gewartet).", "Erklärung der Schwäche": "Lädt wenig, weil kurz gewartet wurde."},
            {"Verfahren": "Früh", "Idee": "Der Bus mit der längsten Standzeit fährt weiter.", "Erklärung der Schwäche": "Entlädt Busse mit viel Ladezeit zuerst; nutzt Wartezeit ungleich."},
            {"Verfahren": "Ladestand max.", "Idee": "Der Bus mit dem höchsten Ladestand bei Abfahrt (nach dem Laden) fährt weiter.", "Erklärung der Schwäche": "Schiebt Fahrten auf volle Busse; bei Gleichstand entscheidet nur die Reihenfolge."},
            {"Verfahren": "Ladestand min.", "Idee": "Der Bus mit dem niedrigsten noch ausreichenden Ladestand fährt weiter.", "Erklärung der Schwäche": "Spart volle Busse für lange Ketten auf, riskiert aber knappe Ketten."},
            {"Verfahren": "Dieselplan, dann trennen", "Idee": "Den Dieselumlauf (Matching) nehmen und die Kette dort trennen, wo die Batterie nicht reicht; ein neuer voller Bus fährt weiter.", "Erklärung der Schwäche": "Das Matching kennt die Batterie nicht und legt lange Ketten an."},
        ]
        if mess is not None:
            for row, key in zip(expl, ("spaet", "frueh", "soc_max", "soc_min", "diesel_trennen")):
                row["Gemessen (Messreihe)"] = mess["regeln"]["per_rule"][key]["kurz"]
        st.dataframe(pd.DataFrame(expl), hide_index=True, width="stretch")
    with tab_exact:
        st.markdown(
            f"**CP-SAT (OR-Tools)** löst ein ganzzahliges Modell: je Anschluss eine Ja/Nein-Variable, je Fahrt der Ladestand bei Abfahrt, Ziel: die wenigsten Busse. Mit begrenzten Ladeplätzen "
            f"kommt je Anschluss die Entscheidung „laden oder nicht“ dazu, und je Haltepunkt gilt: höchstens so viele Ladevorgänge gleichzeitig wie Plätze. Zeitlimit hier {C.EXACT_TIME_LIMIT_S:.0f} s, "
            f"höchstens {C.EXACT_WORKERS} Arbeiter, die beste Regel als Startlösung. **Ohne Beweis** steht die Zahl als obere Schranke da („nicht bewiesen“) mit der bewiesenen unteren Schranke, "
            "nie als Optimum. Die Rechnung rundet in 0,01 kWh zugunsten der Vorsicht (Verbrauch auf, Ladung ab); ein Prüfer rechnet jede Lösung in Fließkomma nach (mit denselben Energie- und Ladedefinitionen, aber ohne diese Rundung und unabhängig von den Löservariablen)."
        )
        st.markdown(f"Aktuell: Status **{res.status}**, Zielwert {res.value if res.value is not None else '–'}, bewiesene untere Schranke {res.bound if res.bound is not None else '–'}, Rechenzeit {T.f1(res.seconds)} s.")
    with tab_base:
        ok, why = DS.verify_diesel_proof(inst, D)
        st.markdown(
            "**Dieselumlauf = n − Matching** (minimale Wegeüberdeckung des Fahrtengraphen, wörtlich aus der Demo „Fahrzeugflotte am Kai“ übernommen): Jede Fahrt wird mit höchstens einer "
            "Nachfolgefahrt verbunden, ein Bus fährt eine Kette. Der **Beweis** ist eine Knotenüberdeckung gleicher Größe wie das Matching (Satz von König): "
            f"{D.matching_size} Verbindungen, {D.cover_size} Überdeckungsknoten, {D.buses} Busse. Prüfung ohne Löser: {why}"
        )

with st.expander("🚧 Wo die Annahmen enden"):
    st.markdown(T.grenzen_markdown(mess) if mess is not None else "Die Messreihe fehlt.")

with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/elektrobus-umlauf-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind die Fahrten mit Abfahrt, Ankunft und Strecke, die erlaubten Anschlüsse, die Batterie $C$ und die Ladeleistung $P$. Gesucht ist eine Zerlegung der Fahrten in möglichst wenige Ketten, eine Kette je Bus, bei der jeder Bus seine Batteriegrenze einhält.

| Symbol | Bedeutung |
|---|---|
| $i$, $j$, $T$ | Fahrt, Menge der Fahrten |
| $A$ | zulässige Anschlüsse: Fahrt $j$ darf auf Fahrt $i$ folgen |
| $a_i$, $b_i$, $d_i$ | Abfahrt, Ankunft und Strecke der Fahrt $i$ |
| $C$, $\rho$ | Batterie, Reserve ($10\,\%$ von $C$) |
| $\varphi$ | Verbrauchsfaktor (1 im Sommer, 1,36 im Winter) |
| $e_i$, $e_{ij}$ | Energie der Fahrt $i$, Energie der Leerfahrt zwischen $i$ und $j$ |
| $P$, $s_{ij}$, $g_{ij}$ | Ladeleistung, Zeitspielraum des Anschlusses in Minuten (nicht der Ladestand $s_j$), Ladegewinn des Anschlusses |
| $x_{ij}$, $y_j$ | 1, wenn ein Bus nach Fahrt $i$ die Fahrt $j$ fährt; 1, wenn Fahrt $j$ einen neuen Bus beginnt |
| $s_j$ | Ladestand bei Abfahrt der Fahrt $j$ (kWh) |
| $c_{ij}$, $K$ | 1, wenn auf dem Anschluss geladen wird (nur bei Platzgrenze); Ladeplätze je Endhaltepunkt |
| $F$ | größte erlaubte Zahl von Bussen bei der gemischten Flotte |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/elektrobus-umlauf-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        "**Gegeben:** Fahrten $i \\in T$ mit Abfahrt $a_i$, Ankunft $b_i$ und Strecke $d_i$; zulässige Anschlüsse $A \\subseteq T \\times T$ (Fahrt $j$ darf auf $i$ folgen, wenn Leerfahrt und "
        "Wendezeit in die Wartezeit passen); Batterie $C$, Reserve $\\rho = 0{,}1\\,C$, Verbrauch $e_i = 1{,}3\\,\\varphi\\,d_i$ (Faktor $\\varphi$: 1 im Sommer, 1,36 im Winter), Leerfahrtenergie $e_{ij}$, "
        "Ladegewinn $g_{ij} = P \\cdot \\max(0,\\, s_{ij} - 3)/60$ mit dem Zeitspielraum $s_{ij}$ in Minuten (nur wo ein Lader steht). **Gesucht:** eine Zerlegung der Fahrten in möglichst wenige Ketten."
    )
    st.markdown(
        "| Symbol | Bedeutung |\n|---|---|\n| $x_{ij}$ | 1, wenn ein Bus nach Fahrt $i$ die Fahrt $j$ fährt |\n| $y_j$ | 1, wenn Fahrt $j$ ein neuer Bus beginnt |\n"
        "| $s_j$ | Ladestand bei Abfahrt der Fahrt $j$ (kWh) |\n| $c_{ij}$ | 1, wenn auf dem Anschluss geladen wird (nur bei Platzgrenze) |\n| $K$ | Ladeplätze je Endhaltepunkt |"
    )
    st.latex(r"\min \sum_{j} y_j")
    st.latex(r"\sum_{i} x_{ij} + y_j = 1 \quad \forall j, \qquad \sum_{j} x_{ij} \le 1 \quad \forall i")
    st.latex(r"x_{ij} = 1 \;\Rightarrow\; s_i - e_i - e_{ij} \ge \rho, \qquad s_j \le s_i - e_i - e_{ij} + g_{ij}\,c_{ij}")
    st.latex(r"e_j + \rho \le s_j \le C \quad \forall j, \qquad x_{ij},\, y_j,\, c_{ij} \in \{0,1\}, \qquad c_{ij} \le x_{ij}")
    st.latex(r"\#\{(i,j) : c_{ij} = 1 \text{ am Endhaltepunkt } h \text{ mit Wartezeit über } t\} \le K \quad \forall h,\ t")
    st.markdown(
        "Ohne Batteriegrenze entfallen die Energiebedingungen; übrig bleibt die minimale Wegeüberdeckung: kleinste Zahl von Ketten $= n - $ größtes Matching im Anschlussgraphen. "
        "Mit Batteriegrenze ist das Modell kein Matching mehr (die Literatur zum Elektrobus-Umlauf nennt es NP-schwer; aus dem Gedächtnis, nicht geprüft, hier nicht bewiesen). Die gemischte Flotte lässt je Kette Diesel (ohne Energiebedingungen) oder Elektro zu und "
        "minimiert die Zahl der Dieselketten bei höchstens $F$ Ketten insgesamt. Der Ladestand $s_j$ ist nach oben durch $C$ begrenzt: geladen wird höchstens bis zur vollen Batterie. "
        "Die Platzbedingung belegt je Ladevorgang das ganze Wartezeitfenster am Haltepunkt (Annahme)."
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zu den Demos: [Interaktive Demos](https://sebastianhanisch.net/demos.html)."
)
