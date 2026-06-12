"""Unit tests for AkeneoClient pure summarizer helpers."""

from akeneo_mcp.akeneo import AkeneoClient


def _product(**overrides):
    item = {
        "identifier": None,
        "uuid": "000008be-fa0f-4f60-b1d4-e3c2963623c0",
        "family": None,
        "enabled": True,
        "categories": [],
        "values": {},
    }
    item.update(overrides)
    return item


class TestSummarizeProductIdentifier:
    def test_identifier_passes_through_when_present(self):
        item = _product(identifier="ABC123")
        assert AkeneoClient._summarize_product(item)["identifier"] == "ABC123"

    def test_identifier_hoisted_from_sku_value_when_null(self):
        item = _product(values={"sku": [{"locale": None, "scope": None, "data": "RC26901"}]})
        assert AkeneoClient._summarize_product(item)["identifier"] == "RC26901"

    def test_identifier_stays_null_without_sku(self):
        item = _product(values={"name": [{"locale": None, "scope": None, "data": "Widget"}]})
        assert AkeneoClient._summarize_product(item)["identifier"] is None

    def test_detail_identifier_hoisted_from_sku_value_when_null(self):
        item = _product(values={"sku": [{"locale": None, "scope": None, "data": "RC26901"}]})
        assert AkeneoClient._summarize_product_detail(item)["identifier"] == "RC26901"

    def test_detail_identifier_passes_through_when_present(self):
        item = _product(identifier="ABC123", values={"sku": [{"data": "OTHER"}]})
        assert AkeneoClient._summarize_product_detail(item)["identifier"] == "ABC123"


class TestCollectionEnvelope:
    def test_count_uses_items_count_when_present(self):
        body = {"items_count": 56481, "_links": {}}
        envelope = AkeneoClient._collection_envelope(body, items=[{}, {}])
        assert envelope["count"] == 2
        assert envelope["total_count"] == 56481

    def test_total_count_omitted_when_absent(self):
        body = {"_links": {"next": {"href": "http://x/next"}}}
        envelope = AkeneoClient._collection_envelope(body, items=[{}, {}, {}])
        assert envelope["count"] == 3
        assert "total_count" not in envelope
        assert envelope["next"] == "http://x/next"

    def test_empty_body(self):
        envelope = AkeneoClient._collection_envelope({}, items=[])
        assert envelope == {"count": 0, "next": None, "previous": None}
