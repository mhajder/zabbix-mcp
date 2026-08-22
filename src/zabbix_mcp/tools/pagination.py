"""
Client-side pagination for Zabbix ``*.get`` methods.

The Zabbix API has no ``offset`` (or cursor) parameter - it only has ``limit``,
and it silently ignores unknown options, so sending ``offset`` returns the first
page over and over. Pages are therefore assembled here:

1. ``countOutput`` for the true total. Zabbix ignores ``limit`` for counting, so
   this reports every matching record, not just the current page.
2. An id-only query limited to ``offset + limit``, sliced locally to get the ids
   for the requested page. Ids are a few bytes each, so this stays cheap.
3. One fetch of the full objects for those ids, reordered to match the cursor
   because ``<object>ids`` is a filter and does not preserve argument order.

Sorting is kept separate from the filters throughout: Zabbix fails with
"Database error occurred." when ``countOutput`` is combined with ``sortfield``,
so the count query must never carry one. A deterministic sort is still required
for pages to line up, so callers pass one in ``sort``.
"""

from typing import Any


async def fetch_total(api_object: Any, filters: dict[str, Any]) -> int:
    """Count the records matching ``filters``.

    Args:
        api_object: Zabbix API object to query, e.g. ``api.host``.
        filters: Params that select which records match. Must not contain
            ``sortfield`` - Zabbix rejects that alongside ``countOutput``.

    Returns:
        int: Total number of matching records, ignoring any page size.
    """
    return int(await api_object.get(**filters, countOutput=True))


async def fetch_page(
    api_object: Any,
    *,
    filters: dict[str, Any],
    shape: dict[str, Any],
    sort: dict[str, Any],
    id_field: str,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch one page of a Zabbix ``*.get`` method plus the total match count.

    Args:
        api_object: Zabbix API object to query, e.g. ``api.host``.
        filters: Params that select *which* records match (ids, search, filter).
        shape: Params that select *what* is returned per record (output,
            select*). Applied only to the final fetch.
        sort: ``sortfield``/``sortorder`` params. Applied to the row queries but
            never to the count query.
        id_field: Singular id property of the object, e.g. ``"hostid"``. The
            plural filter name is derived from it (``"hostids"``).
        limit: Page size.
        offset: Number of matching records to skip.

    Returns:
        tuple: The page of objects, and the total number of matching records.
    """
    total = await fetch_total(api_object, filters)
    if offset >= total:
        return [], total

    if offset == 0:
        rows = await api_object.get(**filters, **sort, **shape, limit=limit)
        return rows, total

    cursor = await api_object.get(
        **filters, **sort, output=[id_field], limit=offset + limit
    )
    page_ids = [row[id_field] for row in cursor[offset:]]
    if not page_ids:
        return [], total

    # Several objects (hostgroup, user, event, problem, mediatype, script) omit
    # their id unless it is named in 'output', and the id is what orders the page,
    # so request it and drop it again if the caller did not ask for it.
    fetch_shape = dict(shape)
    requested = fetch_shape.get("output")
    borrowed_id = isinstance(requested, list) and id_field not in requested
    if borrowed_id:
        fetch_shape["output"] = [*requested, id_field]

    # The original filters are reapplied: for some objects an id alone is not
    # enough to match the record (problem.get needs 'recent' to return resolved
    # problems, for one), and the page ids simply narrow that same result set.
    rows = await api_object.get(**{**filters, f"{id_field}s": page_ids}, **fetch_shape)
    position = {value: index for index, value in enumerate(page_ids)}
    rows.sort(key=lambda row: position.get(row.get(id_field), len(position)))
    if borrowed_id:
        for row in rows:
            row.pop(id_field, None)
    return rows, total
