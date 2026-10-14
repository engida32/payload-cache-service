SAMPLE = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}


def test_round_trip_matches_sample(client):
    created = client.post("/payload", json=SAMPLE)
    assert created.status_code == 200
    body = created.json()
    assert body["cached"] is False

    fetched = client.get(f"/payload/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["output"] == (
        "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
    )


def test_repeat_request_reuses_id_and_transformer(client, spy):
    first = client.post("/payload", json=SAMPLE).json()
    calls_after_first = list(spy.calls)
    second = client.post("/payload", json=SAMPLE).json()
    assert second["id"] == first["id"]
    assert second["cached"] is True
    assert spy.calls == calls_after_first


def test_only_new_strings_hit_transformer(client, spy):
    client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["c", "d"]})
    assert len(spy.calls) == 4
    client.post("/payload", json={"list_1": ["a", "b"], "list_2": ["e", "f"]})
    assert len(spy.calls) == 6


def test_length_mismatch_is_422(client):
    response = client.post("/payload", json={"list_1": ["a"], "list_2": ["a", "b"]})
    assert response.status_code == 422


def test_empty_lists_yield_empty_output(client):
    body = client.post("/payload", json={"list_1": [], "list_2": []}).json()
    assert client.get(f"/payload/{body['id']}").json()["output"] == ""


def test_unknown_id_is_404(client):
    assert client.get("/payload/does-not-exist").status_code == 404


def test_unicode_transform(client):
    body = client.post("/payload", json={"list_1": ["caf\u00e9"], "list_2": ["\U0001f600"]}).json()
    assert client.get(f"/payload/{body['id']}").json()["output"] == "CAF\u00c9, \U0001f600"


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
