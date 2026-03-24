from app.ingestor.local_weather import _extract_kma, _is_korea


def test_is_korea_bounds() -> None:
    assert _is_korea(37.5, 127.0) is True
    assert _is_korea(40.0, 127.0) is False


def test_extract_kma() -> None:
    payload = {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {"category": "SKY", "fcstValue": "3"},
                        {"category": "REH", "fcstValue": "64"},
                        {"category": "TMP", "fcstValue": "11"},
                        {"category": "WSD", "fcstValue": "2.7"},
                        {"category": "POP", "fcstValue": "70"},
                        {"category": "PCP", "fcstValue": "1.0~4.0mm"},
                    ]
                }
            }
        }
    }
    cloud, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_kma(payload)
    assert cloud == 60.0
    assert humidity == 64.0
    assert temp_c == 11.0
    assert wind_mps == 2.7
    assert precip_prob_pct == 70.0
    assert precip_mm == 2.5
