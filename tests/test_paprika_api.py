"""Unit tests for the extended Paprika API client's wire-format helpers.

These test the shape of what gets sent, against a fake `Remote` whose
`_request` is mocked -- no real network calls, no real Paprika account.
"""

from __future__ import annotations

import gzip
import json
from unittest.mock import MagicMock

import pytest

from paprika_mcp import paprika_api


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def make_fake_remote(response_payload):
    remote = MagicMock()
    remote._request.return_value = FakeResponse(response_payload)
    return remote


def _decode_posted_payload(call_args):
    _, body = call_args.kwargs["files"]["data"]
    return json.loads(gzip.decompress(body))


def test_get_result_unwraps_envelope():
    remote = make_fake_remote({"result": [{"uid": "abc"}]})
    result = paprika_api._get_result(remote, "/api/v2/sync/categories/")
    assert result == [{"uid": "abc"}]
    remote._request.assert_called_once_with("get", "/api/v2/sync/categories/")


def test_post_array_sends_gzip_multipart():
    remote = make_fake_remote({"result": True})
    payload = [{"uid": "abc", "name": "milk"}]

    paprika_api._post_array(remote, "/api/v2/sync/groceries/", payload)

    call_args = remote._request.call_args
    assert call_args.args == ("post", "/api/v2/sync/groceries/")
    assert _decode_posted_payload(call_args) == payload


def test_add_groceries_shape():
    remote = make_fake_remote({"result": True})
    paprika_api.add_groceries(
        remote,
        [{"name": "Milk"}, {"name": "Eggs", "quantity": "12"}],
        list_uid="LIST-1",
    )

    payload = _decode_posted_payload(remote._request.call_args)

    assert len(payload) == 2
    assert payload[0]["name"] == "Milk"
    assert payload[0]["aisle"] == ""  # left empty for Paprika auto-assignment
    assert payload[0]["ingredient"] == "milk"
    assert payload[0]["list_uid"] == "LIST-1"
    assert payload[0]["purchased"] is False
    assert payload[1]["quantity"] == "12"


def test_plan_meal_shape():
    remote = make_fake_remote({"result": True})
    paprika_api.plan_meal(
        remote, date="2026-12-25", meal_type="dinner", recipe_uid="RECIPE-1"
    )

    payload = _decode_posted_payload(remote._request.call_args)

    assert len(payload) == 1
    entry = payload[0]
    assert entry["date"] == "2026-12-25 00:00:00"
    assert entry["type"] == 2  # dinner
    assert entry["recipe_uid"] == "RECIPE-1"
    assert entry["deleted"] is False


def test_plan_meal_requires_recipe_or_name():
    remote = make_fake_remote({"result": True})
    with pytest.raises(ValueError):
        paprika_api.plan_meal(remote, date="2026-12-25", meal_type="dinner")


def test_plan_meal_rejects_bad_meal_type():
    remote = make_fake_remote({"result": True})
    with pytest.raises(ValueError):
        paprika_api.plan_meal(
            remote, date="2026-12-25", meal_type="brunch", name="Waffles"
        )


def test_check_off_groceries_preserves_other_fields():
    remote = make_fake_remote({"result": True})
    existing_item = {
        "uid": "ITEM-1",
        "name": "Flour",
        "purchased": False,
        "aisle": "Baking",
        "list_uid": "LIST-1",
    }
    paprika_api.check_off_groceries(remote, [existing_item], purchased=True)

    payload = _decode_posted_payload(remote._request.call_args)
    assert payload[0]["purchased"] is True
    assert payload[0]["aisle"] == "Baking"  # untouched
    assert payload[0]["name"] == "Flour"


def test_get_default_grocery_list_uid_prefers_default():
    remote = make_fake_remote(
        {
            "result": [
                {"uid": "LIST-A", "is_default": False},
                {"uid": "LIST-B", "is_default": True},
            ]
        }
    )
    assert paprika_api.get_default_grocery_list_uid(remote) == "LIST-B"


def test_get_default_grocery_list_uid_falls_back_to_first():
    remote = make_fake_remote({"result": [{"uid": "LIST-A", "is_default": False}]})
    assert paprika_api.get_default_grocery_list_uid(remote) == "LIST-A"


def test_get_default_grocery_list_uid_empty():
    remote = make_fake_remote({"result": []})
    assert paprika_api.get_default_grocery_list_uid(remote) is None
