import numpy as np
from astropy.table import Table

from api.tap import (
    astropy_table_to_list,
    build_select_query,
    build_spatial_icrs_condition,
    build_time_overlap_condition,
    build_where_clause,
)


def test_builders_render_expected_sql():
    s = build_spatial_icrs_condition(10.0, 20.0, 5.5)
    assert "CONTAINS(POINT('ICRS', s_ra, s_dec)" in s
    assert "CIRCLE('ICRS', 10.0, 20.0, 5.5)" in s

    t = build_time_overlap_condition(59000.0, 59001.0)
    assert "t_min < 59001.0 AND t_max > 59000.0" in t

    w = build_where_clause(["a=1", "  ", None, "b=2"])
    assert w == "a=1 AND b=2"
    assert build_where_clause([]) == "1=1"

    q = build_select_query("ivoa.obscore", "1=1", limit=123, columns="*")
    assert q.startswith("SELECT TOP 123")
    assert "FROM ivoa.obscore WHERE 1=1" in q


def test_astropy_table_to_list_conversions():
    table = Table(
        names=("i", "f", "b", "s"),
        dtype=(int, float, "S5", "U10"),
        rows=[
            (1, np.nan, b"abc", "ok"),
            (2, float("inf"), b"\xff\xfe", "ok2"),
        ],
        masked=True,
    )
    # Mask a value as example
    table["i"].mask = [False, True]

    cols, rows = astropy_table_to_list(table)
    assert cols == ["i", "f", "b", "s"]
    # Masked int -> None
    assert rows[1][0] is None
    # NaN/Inf -> None
    assert rows[0][1] is None and rows[1][1] is None
    # Bytes decode best-effort (bad bytes -> repr)
    assert rows[0][2] == "abc"
    assert isinstance(rows[1][2], str)
