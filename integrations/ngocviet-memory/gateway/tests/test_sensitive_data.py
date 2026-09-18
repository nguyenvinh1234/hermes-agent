from app.sensitive_data import detect_secret


def test_detects_private_key_block():
    text = "here is the key:\n-----BEGIN PRIVATE KEY-----\nMIIBVQ...\n-----END PRIVATE KEY-----"
    assert detect_secret(text) is not None


def test_detects_openai_style_key():
    assert detect_secret("use sk-abcdefghijklmnopqrstuvwx to call the API") is not None


def test_detects_github_pat():
    assert detect_secret("token: ghp_1234567890abcdefghij1234567890abcd") is not None


def test_detects_bearer_token():
    assert detect_secret("Authorization: Bearer abcdefghij1234567890") is not None


def test_detects_generic_password_assignment():
    assert detect_secret("db password=SuperSecret123!") is not None


def test_allows_ordinary_business_fact():
    assert detect_secret("Hermes is the central orchestration hub for Ngoc Viet.") is None


def test_allows_short_benign_text():
    assert detect_secret("OK, thanks!") is None
