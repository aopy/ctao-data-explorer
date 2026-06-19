from __future__ import annotations

import urllib.parse
from typing import Any


def augment_with_datalink(
    columns: list[str],
    data: list[list[Any]],
) -> tuple[list[str], list[list[Any]]]:
    if "obs_publisher_did" not in columns:
        return columns, data

    datalink_col = "datalink_url"
    columns_with = columns[:]

    if datalink_col not in columns_with:
        columns_with.append(datalink_col)

    did_idx = columns_with.index("obs_publisher_did")
    datalink_idx = columns_with.index(datalink_col)

    new_rows: list[list[Any]] = []

    for original_row in data:
        new_row = original_row[:]

        while len(new_row) < len(columns_with):
            new_row.append(None)

        did = new_row[did_idx] if did_idx < len(new_row) else None

        if did:
            encoded_did = urllib.parse.quote(str(did), safe="")
            new_row[datalink_idx] = f"/api/datalink?ID={encoded_did}"

        new_rows.append(new_row)

    return columns_with, new_rows
