EMPLOYEE_BAND_LABELS: dict[str, str] = {
    "00": "0",
    "01": "1-2",
    "02": "3-5",
    "03": "6-9",
    "11": "10-19",
    "12": "20-49",
    "21": "50-99",
    "22": "100-199",
    "31": "200-249",
    "32": "250-499",
    "41": "500-999",
    "42": "1000-1999",
    "51": "2000-4999",
    "52": "5000-9999",
    "53": "10000+",
    "NN": "unknown",
}

def employee_band_label(code: str | None) -> str | None:
    if code is None:
        return None
    return EMPLOYEE_BAND_LABELS.get(code, code)
