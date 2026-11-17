"""End-to-end (AppTest): die vier Kernfragen mit ihren Knöpfen, alle Auswahlregler, Permalink, Randeinstellungen. Zeitlimits kurz (conftest.py): geprüft wird, dass
nichts abstürzt und die richtigen Texte erscheinen, nicht, dass jede Rechnung bewiesen ist."""

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ebu_constants as C

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))


def _run(**state):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _texts(at):
    return " ".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [e.value for e in at.info] + [e.value for e in at.warning]
                    + [e.value for e in at.success] + [e.value for e in at.error])


def _metrics(at):
    return {m.label: m.value for m in at.metric}


def test_default_page_shows_four_metrics_a_verdict_and_the_four_questions():
    at = _run()
    labels = list(_metrics(at))
    assert labels[0] == "Dieselumlauf" and labels[-1] == "Nutzbare Batterie"
    assert any(l.startswith("Elektro-Umlauf") for l in labels)
    text = _texts(at)
    for n in range(1, 5):
        assert f"Kernfrage {n}:" in text
    assert "unabhängigen Fließkomma-Prüfer angenommen" in text


def test_expanders_are_found_by_title_not_by_index():
    at = _run()
    titles = [e.label for e in at.expander]
    for want in ("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", "🚧 Wo die Annahmen enden", "📐 Mathematische Formulierung"):
        assert want in titles
    assert titles[-1] == "📐 Mathematische Formulierung"        # Formeln zuletzt (DEMO-PLAYBOOK §2)


def test_ramp_button_computes_the_grid_on_this_timetable():
    at = _run()
    at.button(key="ramp_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert "Zellen bewiesen" in _texts(at) and at.session_state["ramp_done"] is not None


def test_slots_button_compares_one_two_and_unlimited_places():
    at = _run(p_slider=20)
    at.button(key="slots_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert any(set(df.value.columns) >= {"Ladeplätze", "Busse", "Aufschlag", "Status"} for df in at.dataframe)


def test_slots_question_without_charging_power_explains_why_there_is_nothing_to_compare():
    at = _run(p_slider=0)
    assert "Ohne Ladeleistung (P = 0)" in _texts(at)
    assert "slots_start" not in [b.key for b in at.button]


def test_hybrid_button_names_fleet_size_and_diesel_buses():
    at = _run(c_slider=60, season_radio="Winter", p_slider=20, reserve_slider=1)
    at.button(key="hybrid_start").click().run(timeout=TIMEOUT)
    assert not at.exception, [str(e) for e in at.exception]
    assert "Flottengröße von" in _texts(at) and "Dieselmindestflotte" in _texts(at)


@pytest.mark.parametrize("state", [
    dict(season_radio="Winter"), dict(chargers_radio="nur A"), dict(slots_select=1), dict(slots_select=2), dict(slots_select=3),
    dict(timetable_radio="takt"), dict(reserve_slider=3), dict(seed_input=0), dict(seed_input=C.SEED_MAX),
    dict(c_slider=C.C_MIN, p_slider=0), dict(c_slider=C.C_MAX, p_slider=C.P_MAX, season_radio="Sommer"), dict(c_slider=C.C_MIN, p_slider=0, season_radio="Winter", timetable_radio="takt"),
])
def test_edge_settings_render_without_exception(state):
    at = _run(**state)
    assert any(m.label.startswith("Elektro-Umlauf") or m.label == "Elektro-Umlauf" for m in at.metric)


def test_every_view_option_renders():
    at = _run()
    options = list(at.selectbox(key="view_plan").options)
    assert len(options) >= 6
    for opt in options:
        at.selectbox(key="view_plan").set_value(opt).run()
        assert not at.exception, (opt, [str(e) for e in at.exception])


def test_permalink_sets_the_controls_and_clamps_them():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.query_params["c"] = "83"
    at.query_params["p"] = "9999"
    at.query_params["zeit"] = "Winter"
    at.query_params["plaetze"] = "2"
    at.query_params["fahrplan"] = "unbekannt"
    at.run()
    assert not at.exception
    assert at.slider(key="c_slider").value == 85 and at.slider(key="p_slider").value == C.P_MAX
    assert at.radio(key="season_radio").value == "Winter" and at.select_slider(key="slots_select").value == 2
    assert at.radio(key="timetable_radio").value == "zufall"       # ungültiger Wert: Standard bleibt


def test_the_page_does_not_claim_more_than_the_demo_size():
    at = _run()
    assert f"höchstens {C.MAX_TRIPS} Fahrten" in _texts(at)
