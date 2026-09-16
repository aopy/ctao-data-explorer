from api.services.cache import build_cache_key_from_adql


def test_cache_key_differs_for_different_tap_urls():
    adql = "SELECT * FROM hess_dr.obscore_sdc"

    key_a = build_cache_key_from_adql(
        adql,
        "https://tap-a.example.org/tap",
    )
    key_b = build_cache_key_from_adql(
        adql,
        "https://tap-b.example.org/tap",
    )

    assert key_a != key_b


def test_cache_key_is_stable_for_same_tap_url_and_query():
    adql = "SELECT * FROM hess_dr.obscore_sdc"
    tap_url = "https://tap.example.org/tap"

    assert build_cache_key_from_adql(
        adql,
        tap_url,
    ) == build_cache_key_from_adql(
        adql,
        tap_url,
    )


def test_cache_key_normalizes_trailing_slash():
    adql = "SELECT * FROM hess_dr.obscore_sdc"

    assert build_cache_key_from_adql(
        adql,
        "https://tap.example.org/tap",
    ) == build_cache_key_from_adql(
        adql,
        "https://tap.example.org/tap/",
    )
