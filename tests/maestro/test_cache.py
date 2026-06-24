"""Tests for the seen-id cache."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from maestro.cache import SeenCache
from maestro.models import EmailItem


def _items(*ids):
    return [EmailItem(account="a", source_kind="mock", msg_id=i) for i in ids]


def test_filter_new_and_persist(tmp_path):
    path = tmp_path / "seen.json"
    cache = SeenCache(path)
    items = _items("1", "2", "3")
    assert len(cache.filter_new(items)) == 3
    cache.mark_seen(items)
    cache.save()

    cache2 = SeenCache(path)
    assert cache2.filter_new(items) == []
    assert cache2.filter_new(_items("4")) == _items("4")[:]  # by id equality? compare ids
    assert [i.msg_id for i in cache2.filter_new(_items("1", "4"))] == ["4"]


def test_persist_false_does_not_write(tmp_path):
    path = tmp_path / "seen.json"
    cache = SeenCache(path, persist=False)
    cache.mark_seen(_items("1"))
    cache.save()
    assert not path.exists()


def test_prune_drops_old_entries(tmp_path):
    path = tmp_path / "seen.json"
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps({"seen": {"old": old, "new": new}}), encoding="utf-8")
    cache = SeenCache(path, ttl_days=14)
    cache.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "old" not in data["seen"]
    assert "new" in data["seen"]
