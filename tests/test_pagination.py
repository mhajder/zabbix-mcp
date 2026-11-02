"""Client-side paging: Zabbix has no offset, so pages are assembled from ids."""

import pytest

from tests.conftest import FakeZabbixAPI
from zabbix_mcp.tools import pagination
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total

pytestmark = pytest.mark.asyncio

SORT = {"sortfield": "hostid", "sortorder": "ASC"}


async def page(api, *, offset, limit=2, shape=None, filters=None, **kwargs):
    return await fetch_page(
        api.host,
        filters=filters if filters is not None else {"groupids": ["4"]},
        shape=shape if shape is not None else {"output": "extend"},
        sort=SORT,
        id_field="hostid",
        limit=limit,
        offset=offset,
        **kwargs,
    )


async def test_total_counts_without_sorting():
    """Zabbix fails countOutput combined with sortfield."""
    api = FakeZabbixAPI()
    api.on("host.get", "7")

    assert await fetch_total(api.host, {"groupids": ["4"]}) == 7
    assert api.calls == [("host.get", {"groupids": ["4"], "countOutput": True})]


async def test_first_page_is_one_query():
    api = FakeZabbixAPI()
    rows = [{"hostid": "1"}, {"hostid": "2"}]
    api.queue("host.get", "5", rows)

    assert await page(api, offset=0) == (rows, 5)
    assert api.params("host.get")[1] == {
        "groupids": ["4"],
        **SORT,
        "output": "extend",
        "limit": 2,
    }


async def test_offset_past_the_end_skips_the_row_queries():
    api = FakeZabbixAPI()
    api.queue("host.get", "3")

    assert await page(api, offset=3) == ([], 3)
    assert len(api.calls) == 1


async def test_later_page_reads_ids_then_fetches_them_in_cursor_order():
    api = FakeZabbixAPI()
    cursor = [{"hostid": h} for h in ("1", "2", "3", "4", "5")]
    # Zabbix returns an id filter in its own order, not the cursor's.
    fetched = [{"hostid": "5", "host": "e"}, {"hostid": "3", "host": "c"}]
    api.queue("host.get", "9", cursor, fetched)

    rows, total = await page(
        api, offset=2, limit=3, shape={"output": "extend", "selectTags": "extend"}
    )

    assert total == 9
    assert rows == [{"hostid": "3", "host": "c"}, {"hostid": "5", "host": "e"}]
    count, ids, final = api.params("host.get")
    assert "sortfield" not in count
    assert ids == {"groupids": ["4"], **SORT, "output": ["hostid"], "limit": 5}
    # The original filters stay on: some objects need them to match at all.
    assert final == {
        "groupids": ["4"],
        "hostids": ["3", "4", "5"],
        "output": "extend",
        "selectTags": "extend",
    }


async def test_id_borrowed_for_ordering_is_dropped_again():
    api = FakeZabbixAPI()
    api.queue(
        "host.get",
        "4",
        [{"hostid": "1"}, {"hostid": "2"}, {"hostid": "3"}],
        [{"hostid": "3", "name": "c"}, {"hostid": "2", "name": "b"}],
    )

    rows, _ = await page(api, offset=1, shape={"output": ["name"]})

    assert rows == [{"name": "b"}, {"name": "c"}]
    assert api.params("host.get")[2]["output"] == ["name", "hostid"]


async def test_id_already_requested_is_kept():
    api = FakeZabbixAPI()
    api.queue(
        "host.get",
        "3",
        [{"hostid": "1"}, {"hostid": "2"}],
        [{"hostid": "2", "name": "b"}],
    )

    rows, _ = await page(api, offset=1, shape={"output": ["hostid", "name"]})

    assert rows == [{"hostid": "2", "name": "b"}]
    assert api.params("host.get")[2]["output"] == ["hostid", "name"]


async def test_records_deleted_between_count_and_cursor_give_an_empty_page():
    api = FakeZabbixAPI()
    api.queue("host.get", "5", [{"hostid": "1"}])

    assert await page(api, offset=2) == ([], 5)
    assert len(api.calls) == 2


async def test_row_missing_from_the_cursor_sorts_last():
    api = FakeZabbixAPI()
    api.queue(
        "host.get",
        "3",
        [{"hostid": "1"}, {"hostid": "2"}, {"hostid": "3"}],
        [{"name": "no id"}, {"hostid": "3"}, {"hostid": "2"}],
    )

    rows, _ = await page(api, offset=1)

    assert rows == [{"hostid": "2"}, {"hostid": "3"}, {"name": "no id"}]


def macro_api(cursor, tied=None):
    api = FakeZabbixAPI()
    responses = ["100", cursor]
    if tied is not None:
        responses.append(tied)
    responses.append(
        lambda params: [{"hostmacroid": i} for i in params["hostmacroids"]]
    )
    api.queue("usermacro.get", *responses)
    return api


async def macro_page(api, *, offset, limit, sortorder="ASC"):
    rows, _ = await fetch_page(
        api.usermacro,
        filters={"hostids": ["10"]},
        shape={"output": "extend"},
        sort={"sortfield": "macro", "sortorder": sortorder},
        id_field="hostmacroid",
        limit=limit,
        offset=offset,
        break_ties=True,
    )
    return [row["hostmacroid"] for row in rows]


def macros(*pairs):
    return [{"hostmacroid": i, "macro": m} for i, m in pairs]


async def test_ties_are_put_in_id_order():
    """usermacro.get sorts by macro only; tied rows come back in any order."""
    api = macro_api(
        macros(("9", "{$A}"), ("2", "{$A}"), ("5", "{$B}")),
    )

    # The cursor is shorter than offset + limit, so no tie query is needed.
    assert await macro_page(api, offset=0, limit=5) == ["2", "9", "5"]
    assert len(api.params("usermacro.get")) == 3


async def test_last_group_is_read_in_full_when_the_cut_falls_inside_it():
    cursor = macros(("1", "{$A}"), ("8", "{$B}"))
    tied = macros(("8", "{$B}"), ("3", "{$B}"), ("6", "{$B}"))
    api = macro_api(cursor, tied)

    assert await macro_page(api, offset=1, limit=1) == ["3"]
    tie_query = api.params("usermacro.get")[2]
    assert tie_query == {
        "hostids": ["10"],
        "filter": {"macro": "{$B}"},
        "output": ["hostmacroid", "macro"],
        "limit": pagination.MAX_TIE_GROUP + 1,
    }


async def test_descending_sort_orders_ties_by_descending_id():
    api = macro_api(macros(("2", "{$B}"), ("9", "{$B}"), ("4", "{$A}")))

    assert await macro_page(api, offset=0, limit=5, sortorder="desc") == [
        "9",
        "2",
        "4",
    ]


async def test_huge_last_group_keeps_zabbix_order(monkeypatch):
    monkeypatch.setattr(pagination, "MAX_TIE_GROUP", 2)
    cursor = macros(("1", "{$A}"), ("9", "{$B}"), ("4", "{$B}"))
    tied = macros(("9", "{$B}"), ("4", "{$B}"), ("7", "{$B}"))
    api = macro_api(cursor, tied)

    assert await macro_page(api, offset=0, limit=3) == ["1", "9", "4"]


async def test_empty_tie_broken_page_skips_the_fetch():
    api = FakeZabbixAPI()
    api.queue("usermacro.get", "5", [])

    assert await macro_page(api, offset=0, limit=2) == []
    assert len(api.calls) == 2
