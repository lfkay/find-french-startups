from invest_registry.scoring import employee_band_label


def test_employee_band_label_mapping() -> None:
    assert employee_band_label("12") == "20-49"
    assert employee_band_label("NN") == "unknown"
    assert employee_band_label(None) is None
