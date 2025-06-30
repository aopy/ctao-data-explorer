from authlib.integrations.starlette_client import OAuth
from starlette.config import Config as StarletteConfig

config_env = StarletteConfig(".env")
oauth = OAuth(config_env)

CTAO_PROVIDER_NAME = "ctao"
oauth.register(
    name=CTAO_PROVIDER_NAME,
    server_metadata_url="https://iam-ctao.cloud.cnaf.infn.it/.well-known/openid-configuration",
    client_id=config_env("CTAO_CLIENT_ID"),
    client_secret=config_env("CTAO_CLIENT_SECRET"),
    client_kwargs={"scope": "openid profile email offline_access"},
)
