from app.ingestor.local_weather import _extract_openmeteo, _extract_openweather


def test_extract_openweather() -> None:
    cloud, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_openweather(
        {"clouds": {"all": 42}, "main": {"humidity": 71, "temp": 9}, "wind": {"speed": 1.8}, "rain": {"1h": 0.6}}
    )
    assert cloud == 42.0
    assert humidity == 71.0
    assert temp_c == 9.0
    assert wind_mps == 1.8
    assert precip_prob_pct == 0.0
    assert precip_mm == 0.6


def test_extract_openmeteo() -> None:
    cloud, humidity, temp_c, wind_mps, precip_prob_pct, precip_mm = _extract_openmeteo(
        {
            "current": {
                "cloud_cover": 18,
                "relative_humidity_2m": 63,
                "temperature_2m": 7.5,
                "wind_speed_10m": 3.4,
                "precipitation": 1.2,
            }
        }
    )
    assert cloud == 18.0
    assert humidity == 63.0
    assert temp_c == 7.5
    assert wind_mps == 3.4
    assert precip_prob_pct == 0.0
    assert precip_mm == 1.2
