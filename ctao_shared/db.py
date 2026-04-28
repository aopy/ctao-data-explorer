def _deprecated(*_a, **_kw):  # pragma: no cover
    raise RuntimeError(
        "ctao_shared.db is deprecated. Use api.db / api.redis_client or "
        "auth_service.db / auth_service.redis_client / auth_service.crypto."
    )


get_async_session = _deprecated
get_redis_pool = _deprecated
get_redis_client = _deprecated
encrypt_token = _deprecated
decrypt_token = _deprecated
