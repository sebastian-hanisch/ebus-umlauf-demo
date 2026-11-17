"""Permalink (Begrenzen und Einrasten), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import ebu_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    lo: float | None = None
    hi: float | None = None
    step: float | None = None
    options: tuple | None = None


_D = C.PRESETS[C.DEFAULT_PRESET]
SETTING_SPECS = {
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
    "timetable_radio": SettingSpec("fahrplan", str, _D["timetable"], options=C.TIMETABLES),
    "c_slider": SettingSpec("c", int, _D["c"], C.C_MIN, C.C_MAX, C.C_STEP),
    "season_radio": SettingSpec("zeit", str, _D["season"], options=C.SEASON_OPTIONS),
    "p_slider": SettingSpec("p", int, _D["p"], C.P_MIN, C.P_MAX, C.P_STEP),
    "chargers_radio": SettingSpec("lader", str, _D["chargers"], options=C.CHARGER_OPTIONS),
    "slots_select": SettingSpec("plaetze", int, _D["slots"], options=C.SLOT_OPTIONS),
    "reserve_slider": SettingSpec("reserve", int, _D["reserve_buses"], C.RESERVE_BUSES_MIN, C.RESERVE_BUSES_MAX, 1),
}
PRESET_KEYS = {"seed": "seed_input", "timetable": "timetable_radio", "c": "c_slider", "season": "season_radio", "p": "p_slider",
               "chargers": "chargers_radio", "slots": "slots_select", "reserve_buses": "reserve_slider"}
SETTINGS_FIELD = {v: k for k, v in PRESET_KEYS.items()}   # Reglerschlüssel → Feld in `Settings`


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def clean(spec: SettingSpec, raw):
    """Wert aus der Adresszeile: Typ, Optionen, Grenzen und Rasterschritt; ungültig → None."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if spec.options is not None:
        return value if value in spec.options else None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.lo is not None:
        value = int(spec.lo + round((value - spec.lo) / spec.step) * spec.step)
        value = min(spec.hi, value)
    return value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt und eingerastet."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = clean(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        if key in C.PRESETS[name]:
            st.session_state[state_key] = C.PRESETS[name][key]


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen Standardwert) mit dem Session State."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden (alle Regler bleiben danach frei):")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)


def current_settings_dict(state=None):
    """Aktueller Stand der Regler als {Feld: Wert} (für `Settings(**...)`)."""
    state = st.session_state if state is None else state
    return {field: state.get(key, SETTING_SPECS[key].default) for key, field in SETTINGS_FIELD.items()}
