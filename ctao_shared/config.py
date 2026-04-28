def get_settings():  # pragma: no cover
    raise RuntimeError(
        "ctao_shared.config is deprecated and will be removed in v1.1.0. "
        "Use api.config.get_api_settings or auth_service.config.get_auth_settings."
    )
