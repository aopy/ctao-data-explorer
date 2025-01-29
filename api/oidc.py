from fastapi.responses import RedirectResponse
from .auth import UserTable, fastapi_users
from fastapi_users.db import SQLAlchemyUserDatabase
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session
from .auth import get_jwt_strategy

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
    given_name = userinfo.get("given_name")
    family_name = userinfo.get("family_name")
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
            "is_active": True,
            "first_name": given_name,
            "last_name": family_name,
        }
        new_user = UserTable(**new_data)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        existing_user = new_user
    else:
        # Update user to sync names from CTAO each time
        existing_user.first_name = given_name
        existing_user.last_name = family_name
        await session.commit()
        await session.refresh(existing_user)

    jwt_strategy = get_jwt_strategy()
    local_token = await jwt_strategy.write_token(existing_user)
    # print("DEBUG local_token =>", local_token)

    return RedirectResponse(url=f"/?token={local_token}")
