import payload_cache.services.transformer as transformer_module
from payload_cache.services.transformer import UppercaseTransformer


def test_uppercases_and_counts():
    t = UppercaseTransformer(latency_ms=0)
    assert t.transform("hello") == "HELLO"
    assert t.call_count == 1


def test_batch_counts_each_element():
    t = UppercaseTransformer(latency_ms=0)
    assert t.transform_batch(["a", "b", "c"]) == ["A", "B", "C"]
    assert t.call_count == 3


def test_unicode_uppercase():
    assert UppercaseTransformer().transform("caf\u00e9") == "CAF\u00c9"


def test_latency_is_applied(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(transformer_module, "sleep", lambda s: calls.append(s))
    UppercaseTransformer(latency_ms=250).transform("x")
    assert calls == [0.25]
