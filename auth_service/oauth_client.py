from authlib.integrations.starlette_client import OAuth
from ctao_shared.config import get_settings
from ctao_shared.constants import CTAO_PROVIDER_NAME

settings = get_settings()
oauth = OAuth()

oauth.register(
    name=CTAO_PROVIDER_NAME,
    server_metadata_url=settings.OIDC_SERVER_METADATA_URL,
    client_id=settings.CTAO_CLIENT_ID,
    client_secret=settings.CTAO_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email offline_access"},
)
