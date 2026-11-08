from medflock.response_checks import unit_warnings


def test_troponin_unit_change_is_visible_without_rewriting_answer():
    source = "hs-troponin I 11 ng/L (upper reference limit 19 ng/L)"
    assert not unit_warnings(source, "Troponin I 11 ng/L, reference 19 ng/L")
    warnings = unit_warnings(source, "Troponin I 11 ng/mL, reference 19 ng/mL")
    assert len(warnings) == 2
    assert "11 ng/mL" in warnings[0] and "ng/l" in warnings[0]


def test_check_does_not_invent_source_units():
    assert not unit_warnings("Troponin unavailable", "Troponin 11 ng/L")
