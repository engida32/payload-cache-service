"""Deterministic payload identity.

The id is derived from the *input* (never the output) so a repeat request can be
served before any transform runs. CACHE_VERSION is part of the hashed material,
so changing the transformer or payload format invalidates old ids instead of
returning stale output.
"""

import hashlib
import json


def canonical_payload(list_1: list[str], list_2: list[str], version: int) -> str:
    return json.dumps(
        {"v": version, "list_1": list_1, "list_2": list_2},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def payload_id(list_1: list[str], list_2: list[str], version: int) -> str:
    canonical = canonical_payload(list_1, list_2, version)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
