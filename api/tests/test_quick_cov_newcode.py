import numpy as np
import pytest
from astropy.table import Table

from api.services.object_lookup import (
    adql_escape,
    catalog_variants,
    is_short_catalog,
)
from api.tap import astropy_table_to_list


def test_adql_escape_and_short_catalog():
    assert adql_escape("O'Hare") == "O''Hare"
    assert is_short_catalog("M42")
    assert is_short_catalog("NGC6543")
    assert not is_short_catalog("NotACatalog")


def test_catalog_variants_spacing():
    # M  42 / M   42 variants are generated
    variants = list(catalog_variants("M42"))
    assert any(v.startswith("M ") for v in variants)
    assert any(v.startswith("M  ") for v in variants)


def test_astropy_table_to_list_typing_and_edge():
    # build a small table with different dtypes, NaN, masked values etc.
    t = Table()
    t["a"] = [1, 2]
    t["b"] = np.array([1.5, np.nan], dtype=float)
    t["c"] = np.array([b"x", b"y"])
    m = np.ma.array([10, 20], mask=[False, True])
    t["masked"] = m

    cols, rows = astropy_table_to_list(t)
    assert cols == ["a", "b", "c", "masked"]
    assert rows[0][0] == 1
    assert rows[0][1] == pytest.approx(1.5)
    assert rows[0][2] == "x"
    assert rows[0][3] == 10
    # second row has NaN -> None, masked -> None
    assert rows[1][1] is None
    assert rows[1][3] is None
