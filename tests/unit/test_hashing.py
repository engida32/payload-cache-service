from payload_cache.core.hashing import canonical_payload, payload_id


def test_deterministic():
    a = payload_id(["x"], ["y"], 1)
    b = payload_id(["x"], ["y"], 1)
    assert a == b
    assert len(a) == 32


def test_order_sensitive():
    assert payload_id(["x"], ["y"], 1) != payload_id(["y"], ["x"], 1)


def test_version_sensitive():
    assert payload_id(["x"], ["y"], 1) != payload_id(["x"], ["y"], 2)


def test_unicode_not_escaped():
    canonical = canonical_payload(["café"], ["😀"], 1)
    assert "café" in canonical and "😀" in canonical


def test_structurally_stable():
    # compact separators, sorted keys
    assert canonical_payload(["a"], ["b"], 1) == '{"list_1":["a"],"list_2":["b"],"v":1}'
