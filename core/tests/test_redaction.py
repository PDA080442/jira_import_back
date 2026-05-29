from core.logging import redact_mapping


def test_redact_mapping():
    result = redact_mapping({"authorization": "Bearer token", "count": 1})

    assert result["authorization"] == "***REDACTED***"
    assert result["count"] == 1
