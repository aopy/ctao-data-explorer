import allure
from fastapi.testclient import TestClient

from api.load_testing import FIELD_NAMES, _selected_columns, create_tap_app, synthetic_obscore
from api.mock_storage import app as storage_app


def test_synthetic_obscore_is_deterministic_and_reuses_blob_classes():
    with allure.step("Generate the full deterministic ObsCore corpus"):
        rows = synthetic_obscore(50_000)

    with allure.step("Verify record identity, tile coverage, and blob reuse"):
        assert len(rows) == 50_000
        assert len({row["obs_id"] for row in rows}) == 50_000
        assert {row["access_estsize"] for row in rows} == {1, 8, 64}
        assert len({(row["s_ra"], row["s_dec"]) for row in rows}) == 500
        assert rows[0]["s_ra"] == 83.63
        assert rows[0]["s_dec"] == 22.01


def test_selected_columns_handles_multiline_top_query():
    with allure.step("Parse a multiline SELECT TOP projection without regex backtracking"):
        assert _selected_columns("SELECT TOP 1\nobs_id, obscore.lfn\nFROM ctao_sdc.obscore") == [
            "obs_id",
            "lfn",
        ]


def test_mock_tap_returns_schema_faithful_votable_and_tap_schema_csv():
    with allure.step("Start a seeded TAP-compatible mock"):
        client = TestClient(create_tap_app(1_000))

    with allure.step("Request the captured TAP schema columns"):
        schema = client.post(
            "/tap/sync",
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "csv",
                "QUERY": "SELECT column_name FROM TAP_SCHEMA.columns",
            },
        )
        assert schema.status_code == 200
        assert schema.text.splitlines()[1:] == list(FIELD_NAMES)

    with allure.step("Request a VOTable result from the mock"):
        response = client.post(
            "/tap/sync",
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "votable",
                "QUERY": "SELECT TOP 100 * FROM ctao_sdc.obscore WHERE 1=1",
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-votable+xml")
        assert "QUERY_STATUS" in response.text
        assert 'name="obs_publisher_did"' in response.text
        assert response.text.count("<TR>") == 100

    with allure.step("Request an unbounded VOTable result from the mock"):
        response = client.post(
            "/tap/sync",
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "votable",
                "QUERY": "SELECT * FROM ctao_sdc.obscore WHERE 1=1",
            },
        )
        assert response.status_code == 200
        assert response.text.count("<TR>") == 1_000

    with allure.step("Query the Crab test coordinates"):
        response = client.post(
            "/tap/sync",
            data={
                "REQUEST": "doQuery",
                "LANG": "ADQL",
                "FORMAT": "votable",
                "QUERY": (
                    "SELECT TOP 100 * FROM ctao_sdc.obscore "
                    "WHERE CONTAINS(POINT('ICRS', s_ra, s_dec), "
                    "CIRCLE('ICRS', 83.63, 22.01, 40)) = 1"
                ),
            },
        )
        assert response.text.count("<TR>") == 100


def test_mock_storage_requires_bearer_and_reuses_size_classes():
    client = TestClient(storage_app)

    with allure.step("Reject a storage request without a bearer token"):
        assert client.get("/objects/5000000001").status_code == 401

    with allure.step("Serve a deterministic dummy blob for an authorized request"):
        response = client.get("/objects/5000000001", headers={"Authorization": "Bearer test"})
        assert response.status_code == 200
        assert int(response.headers["X-Mock-Blob-Size"]) == len(response.content)
