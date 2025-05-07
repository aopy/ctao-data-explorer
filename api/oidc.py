from fastapi.responses import RedirectResponse
from .auth import UserTable, fastapi_users, auth_backend, cookie_transport
from fastapi_users.db import SQLAlchemyUserDatabase
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_async_session
from datetime import datetime
from urllib.parse import urljoin
import os

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
BASE_URL = os.getenv("BASE_URL")

@oidc_router.get("/login")
async def login(request: Request):
    # let FastAPI compute the right path automatically
    callback_url = request.url_for("auth_callback")
    return await oauth.ctao.authorize_redirect(request, callback_url)


@oidc_router.get("/callback")
async def auth_callback(
        request: Request,
        session: AsyncSession = Depends(get_async_session),
):
    try:
        token = await oauth.ctao.authorize_access_token(request)
        userinfo = await oauth.ctao.userinfo(token=token)
    except Exception as e:
        print(f"OIDC Error: {e}")
        raise HTTPException(status_code=400, detail="OIDC authentication failed or was cancelled.")

    email = userinfo.get("email")
    given_name = userinfo.get("given_name")
    family_name = userinfo.get("family_name")
    # sub = userinfo.get("sub") # Not used

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by OIDC provider")

    # Check if user exists or create/update
    user_db = SQLAlchemyUserDatabase(session, UserTable)
    user = await user_db.get_by_email(email)

    if not user:
        # Create new user
        # Generate a dummy password hash, fastapi-users requires it
        dummy_password_hash = fastapi_users.password_helper.hash("a_very_long_random_dummy_password_that_wont_be_used")
        new_data = {
            "email": email,
            "hashed_password": dummy_password_hash,
            "is_active": True,
            "is_verified": True,
            "first_name": given_name,
            "last_name": family_name,
            "first_login_at": datetime.utcnow(),
        }
        user = await user_db.create(new_data)
    else:
        # Update existing user
        update_data = {}
        if user.first_login_at is None:
            update_data["first_login_at"] = datetime.utcnow()
        if user.first_name != given_name:
             update_data["first_name"] = given_name
        if user.last_name != family_name:
             update_data["last_name"] = family_name

        if update_data:
            user = await user_db.update(user, update_data)

    # Generate the JWT token using the strategy from the backend
    strategy = auth_backend.get_strategy()
    token = await strategy.write_token(user) # The actual JWT string

    # Create the RedirectResponse
    redirect_response = RedirectResponse(url="http://localhost:8000/")

    # Use the RedirectResponse's set_cookie method
    redirect_response.set_cookie(
        key=cookie_transport.cookie_name,
        value=token,
        max_age=cookie_transport.cookie_max_age,
        path=cookie_transport.cookie_path,
        domain="localhost",
        secure=cookie_transport.cookie_secure,
        httponly=cookie_transport.cookie_httponly,
        samesite=cookie_transport.cookie_samesite,
    )

    return redirect_response

