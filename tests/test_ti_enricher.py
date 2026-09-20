from ti_enricher import _simulated_score


def test_simulated_score_in_range():
    for domain in ["example.com", "verify-account-now.xyz", "cdn.jsdelivr.net"]:
        score = _simulated_score(domain)
        assert 0 <= score <= 100


def test_simulated_score_is_deterministic():
    assert _simulated_score("example.com") == _simulated_score("example.com")


def test_suspicious_keyword_raises_score():
    suspicious = _simulated_score("verify-account-now.xyz")
    benign = _simulated_score("cdn.jsdelivr.net")
    # Not guaranteed for every hash, but true for these two fixed examples.
    assert suspicious > benign
