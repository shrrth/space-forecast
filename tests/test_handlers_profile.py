from app.bot.handlers import _normalize_equipment, _normalize_lang, _normalize_purpose


def test_normalize_equipment() -> None:
    assert _normalize_equipment("basic") == "basic"
    assert _normalize_equipment("ADVANCED") == "advanced"
    assert _normalize_equipment(" visual ") == "visual"
    assert _normalize_equipment("unknown") is None


def test_normalize_purpose() -> None:
    assert _normalize_purpose("deep_sky") == "deep_sky"
    assert _normalize_purpose("DEEP-SKY") == "deep_sky"
    assert _normalize_purpose("planetary") == "planetary"
    assert _normalize_purpose("widefield") == "widefield"
    assert _normalize_purpose("foo") is None


def test_normalize_lang() -> None:
    assert _normalize_lang("ko") == "ko"
    assert _normalize_lang("en-US") == "en"
    assert _normalize_lang("EN") == "en"
    assert _normalize_lang("jp") is None
