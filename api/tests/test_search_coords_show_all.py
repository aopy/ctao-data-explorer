from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from astropy.table import Table
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services import search_coords as search_coords_module
from api.services.search_coords import (
    SearchCoordsParams,
    search_coords_impl,
)
from api.tap import TapQueryResult


@pytest.fixture
def db_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def result_table() -> Table:
    return Table(
        rows=[
            (
                "obs-001",
                83.63,
                22.01,
                59000.0,
                59000.1,
                0.1,
                10.0,
            ),
            (
                "obs-002",
                120.25,
                -35.4,
                59001.0,
                59001.2,
                0.2,
                20.0,
            ),
        ],
        names=[
            "obs_id",
            "s_ra",
            "s_dec",
            "t_min",
            "t_max",
            "em_min",
            "em_max",
        ],
    )


@pytest.mark.asyncio
async def test_show_all_succeeds_without_search_criteria(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncMock,
    result_table: Table,
) -> None:
    """
    show_all=True must allow an unfiltered search and generate WHERE 1=1.
    """
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        search_coords_module,
        "_discover_tap_columns",
        AsyncMock(
            return_value=(
                True,
                {
                    "obs_id",
                    "s_ra",
                    "s_dec",
                    "t_min",
                    "t_max",
                    "em_min",
                    "em_max",
                },
            )
        ),
    )

    def fake_perform_query(
        fields: dict[str, Any],
        conditions: list[str],
        limit: int | None = None,
    ) -> tuple[str | None, TapQueryResult, str]:
        query = fields["adql_query_str"]["value"]

        captured["query"] = query
        captured["conditions"] = list(conditions)
        captured["limit"] = limit

        return (
            None,
            TapQueryResult(
                table=result_table,
                query=query,
                overflow=False,
            ),
            query,
        )

    monkeypatch.setattr(
        search_coords_module,
        "perform_query_with_conditions",
        fake_perform_query,
    )

    params = SearchCoordsParams(
        show_all=True,
        tap_url="https://example.test/tap",
        obscore_table="example.obscore",
    )

    result = await search_coords_impl(
        params=params,
        identity=None,
        db_session=db_session,
        redis_client=None,
    )

    assert captured["conditions"] == []
    assert captured["limit"] is None
    assert captured["query"] == ("SELECT * FROM example.obscore WHERE 1=1")

    assert result.total_rows == 2
    assert result.truncated is False
    assert result.truncation_message is None
    assert len(result.data) == 2
    assert "obs_id" in result.columns


@pytest.mark.asyncio
async def test_empty_search_without_show_all_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncMock,
) -> None:
    """
    The regular endpoint must still reject requests without any criterion.
    """
    monkeypatch.setattr(
        search_coords_module,
        "_discover_tap_columns",
        AsyncMock(return_value=(True, set())),
    )

    params = SearchCoordsParams(
        show_all=False,
        tap_url="https://example.test/tap",
        obscore_table="example.obscore",
    )

    with pytest.raises(HTTPException) as exc_info:
        await search_coords_impl(
            params=params,
            identity=None,
            db_session=db_session,
            redis_client=None,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == ("Provide at least one search criterion.")


@pytest.mark.asyncio
async def test_show_all_ignores_accidental_filter_parameters(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncMock,
    result_table: Table,
) -> None:
    """
    show_all=True must not apply coordinates, time, energy, or optional filters,
    even if a caller includes them in the same request.
    """
    captured: dict[str, Any] = {}

    monkeypatch.setattr(
        search_coords_module,
        "_discover_tap_columns",
        AsyncMock(
            return_value=(
                True,
                {
                    "s_ra",
                    "s_dec",
                    "energy_min",
                    "energy_max",
                    "proposal_id",
                },
            )
        ),
    )

    def fake_perform_query(
        fields: dict[str, Any],
        conditions: list[str],
        limit: int | None = None,
    ) -> tuple[str | None, TapQueryResult, str]:
        query = fields["adql_query_str"]["value"]

        captured["query"] = query
        captured["conditions"] = list(conditions)

        return (
            None,
            TapQueryResult(
                table=result_table,
                query=query,
                overflow=False,
            ),
            query,
        )

    monkeypatch.setattr(
        search_coords_module,
        "perform_query_with_conditions",
        fake_perform_query,
    )

    params = SearchCoordsParams(
        show_all=True,
        coordinate_system="deg",
        ra=83.63,
        dec=22.01,
        search_radius=1.0,
        mjd_start=59000.0,
        mjd_end=59001.0,
        energy_min=0.5,
        energy_max=5.0,
        proposal_id="proposal-123",
        tap_url="https://example.test/tap",
        obscore_table="example.obscore",
    )

    result = await search_coords_impl(
        params=params,
        identity=None,
        db_session=db_session,
        redis_client=None,
    )

    assert captured["conditions"] == []
    assert captured["query"] == ("SELECT * FROM example.obscore WHERE 1=1")
    assert result.total_rows == 2


@pytest.mark.asyncio
async def test_show_all_preserves_tap_overflow_warning(
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncMock,
    result_table: Table,
) -> None:
    """
    A TAP-side MAXREC truncation must still be exposed to the frontend.
    """
    monkeypatch.setattr(
        search_coords_module,
        "_discover_tap_columns",
        AsyncMock(return_value=(True, set())),
    )

    def fake_perform_query(
        fields: dict[str, Any],
        conditions: list[str],
        limit: int | None = None,
    ) -> tuple[str | None, TapQueryResult, str]:
        query = fields["adql_query_str"]["value"]

        return (
            None,
            TapQueryResult(
                table=result_table,
                query=query,
                overflow=True,
            ),
            query,
        )

    monkeypatch.setattr(
        search_coords_module,
        "perform_query_with_conditions",
        fake_perform_query,
    )

    params = SearchCoordsParams(
        show_all=True,
        tap_url="https://example.test/tap",
        obscore_table="example.obscore",
    )

    result = await search_coords_impl(
        params=params,
        identity=None,
        db_session=db_session,
        redis_client=None,
    )

    assert result.total_rows == 2
    assert result.truncated is True
    assert result.truncation_message is not None
    assert "QUERY_STATUS=OVERFLOW" in result.truncation_message
    assert "2 rows" in result.truncation_message
