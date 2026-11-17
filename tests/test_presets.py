"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen; Permalink begrenzt, rastet ein und verwirft Ungültiges."""

import dataclasses

import ebu_constants as C
import ebu_evaluation as ev
import ebu_presets as P


def test_every_preset_has_help_and_all_keys():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    for name, preset in C.PRESETS.items():
        assert set(preset) == set(P.PRESET_KEYS), name
        assert C.PRESET_HELP[name], name


def test_preset_values_are_valid_for_their_controls():
    for name, preset in C.PRESETS.items():
        for key, state_key in P.PRESET_KEYS.items():
            spec = P.SETTING_SPECS[state_key]
            value = preset[key]
            if spec.options is not None:
                assert value in spec.options, (name, key)
            else:
                assert spec.lo <= value <= spec.hi, (name, key)
                if spec.step:
                    assert (value - spec.lo) % spec.step == 0, (name, key)


def test_default_preset_equals_the_default_settings():
    assert ev.Settings(**C.PRESETS[C.DEFAULT_PRESET]) == ev.Settings()
    assert next(iter(C.PRESETS)) == C.DEFAULT_PRESET       # das Standard-Preset steht zuerst (der Layout-Test erwartet es hervorgehoben)


def test_setting_specs_cover_every_preset_key_and_every_settings_field():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS)
    assert set(P.PRESET_KEYS) == {f.name for f in dataclasses.fields(ev.Settings)}


def test_presets_differ_in_at_least_one_setting():
    values = [tuple(sorted(p.items())) for p in C.PRESETS.values()]
    assert len(set(values)) == len(values)


def test_permalink_values_are_clamped_snapped_and_validated():
    c, p = P.SETTING_SPECS["c_slider"], P.SETTING_SPECS["p_slider"]
    assert P.clean(c, "83") == 85 and P.clean(c, "81") == 80          # rastet auf Vielfache von 5 ein
    assert P.clean(c, "5") == C.C_MIN and P.clean(c, "9999") == C.C_MAX
    assert P.clean(p, "0") == 0 and P.clean(p, "151") == C.P_MAX
    assert P.clean(c, "abc") is None
    assert P.clean(P.SETTING_SPECS["season_radio"], "Frühling") is None and P.clean(P.SETTING_SPECS["season_radio"], "Winter") == "Winter"
    assert P.clean(P.SETTING_SPECS["slots_select"], "2") == 2 and P.clean(P.SETTING_SPECS["slots_select"], "5") is None
    assert P.clean(P.SETTING_SPECS["seed_input"], "-4") == 0
