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

Where the only sortable field is not unique (``usermacro.get`` sorts by
``macro`` alone), rows tied on it can come back in a different order on each
query. ``break_ties`` then puts each group of tied rows in id order - see
_tie_broken_ids.
"""

from typing import Any

# Largest group of tied rows that is read in full to put it in id order. A
# bigger one (one macro name on thousands of hosts) keeps Zabbix's own order on
# that page instead, which can differ between queries.
MAX_TIE_GROUP = 1000


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
    break_ties: bool = False,
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
        break_ties: Order rows tied on the sort field by id, for objects whose
            only sort field is not unique. Costs up to one extra id query of
            at most MAX_TIE_GROUP + 1 rows.

    Returns:
        tuple: The page of objects, and the total number of matching records.
    """
    total = await fetch_total(api_object, filters)
    if offset >= total:
        return [], total

    if break_ties:
        page_ids = await _tie_broken_ids(
            api_object, filters, sort, id_field, limit, offset
        )
    elif offset == 0:
        rows = await api_object.get(**filters, **sort, **shape, limit=limit)
        return rows, total
    else:
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


async def _tie_broken_ids(
    api_object: Any,
    filters: dict[str, Any],
    sort: dict[str, Any],
    id_field: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Return the ids of one page in Zabbix's order, with ties broken by id.

    Rows tied on the sort field come back in any order but always next to each
    other, so every group of equal values in the first ``offset + limit`` rows
    holds all of that value's rows - except the last group, which may continue
    past the cut. Groups are put in id order here, and the last one is read in
    full first with one query for its value - unless it has more than
    MAX_TIE_GROUP rows, in which case it keeps Zabbix's order.

    Args:
        api_object: Zabbix API object to query, e.g. ``api.usermacro``.
        filters: Params that select which records match.
        sort: ``sortfield`` (a single field name) and ``sortorder``.
        id_field: Singular id property of the object.
        limit: Page size.
        offset: Number of matching records to skip.

    Returns:
        list: Ids of the requested page, in page order.
    """
    field = sort["sortfield"]
    descending = str(sort.get("sortorder", "ASC")).upper() == "DESC"
    cursor = await api_object.get(
        **filters, **sort, output=[id_field, field], limit=offset + limit
    )

    groups: list[list[dict[str, Any]]] = []
    for row in cursor:
        if groups and groups[-1][0].get(field) == row.get(field):
            groups[-1].append(row)
        else:
            groups.append([row])

    keep_last_order = False
    if groups and len(cursor) == offset + limit:
        # The cut may fall inside the last group; read all of it, unless it is
        # too big to be worth reading on every page.
        value = groups[-1][0].get(field)
        tie_filter = {**filters.get("filter", {}), field: value}
        tied = await api_object.get(
            **{**filters, "filter": tie_filter},
            output=[id_field, field],
            limit=MAX_TIE_GROUP + 1,
        )
        if len(tied) <= MAX_TIE_GROUP:
            groups[-1] = tied
        else:
            keep_last_order = True

    ordered: list[str] = []
    for index, group in enumerate(groups):
        if not (keep_last_order and index == len(groups) - 1):
            group = sorted(
                group, key=lambda row: int(row[id_field]), reverse=descending
            )
        ordered.extend(row[id_field] for row in group)
    return ordered[offset : offset + limit]
