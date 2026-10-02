import gui
import fold_designer_bridge as bridge


def test_ui_number_text_hides_float_noise_near_integer():
    noisy = 400.0000000000006
    assert gui.BoxCalculatorGUI._fold_designer_number_text(noisy) == "400"
    assert bridge._setting_number_text(noisy) == "400"


def test_ui_number_text_preserves_real_decimal_value():
    value = 400.25
    assert gui.BoxCalculatorGUI._fold_designer_number_text(value) == "400.25"
    assert bridge._setting_number_text(value) == "400.25"
