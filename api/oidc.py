from fastapi.responses import RedirectResponse
from .auth import UserTable, fastapi_users
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session

# OIDC config
config = Config('.env')
oauth = OAuth(config)

oauth.register(
    name='ctao',
    server_metadata_url=f'https://iam-ctao.cloud.cnaf.infn.it/.well-known/openid-configuration',
    client_id=config("CTAO_CLIENT_ID"),
    client_secret=config("CTAO_CLIENT_SECRET"),
    client_kwargs={
        'scope': 'openid profile email'
    }
)

oidc_router = APIRouter(prefix="/oidc", tags=["oidc"])

@oidc_router.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for('auth_callback')
    print("Redirect URI =>", redirect_uri)
    return await oauth.ctao.authorize_redirect(request, redirect_uri)


@oidc_router.get("/callback")
async def auth_callback(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
):
    token = await oauth.ctao.authorize_access_token(request)
    # userinfo = await oauth.ctao.parse_id_token(request, token)
    userinfo = await oauth.ctao.userinfo(token=token)

    email = userinfo.get("email")
    sub = userinfo.get("sub")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by OIDC provider")

    # Check if user exists
    user_db = SQLAlchemyUserDatabase(session, UserTable)
    existing_user = await user_db.get_by_email(email)

    if not existing_user:
        # Create new user
        new_data = {
            "email": email,
            "hashed_password": "...",  # generate a random password
            "is_active": True
        }
        new_user = UserTable(**new_data)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        existing_user = new_user

    # Generate JWT token
    from fastapi_users.authentication import JWTStrategy
    strategy = JWTStrategy(secret="SECRET_KEY_CHANGE_ME", lifetime_seconds=3600)
    local_token = strategy.write_token(existing_user.id)

    return RedirectResponse(url=f"/?token={local_token}")
