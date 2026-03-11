import bcrypt

from fastapi import FastAPI, HTTPException, Response
from authx import AuthX, AuthXConfig
from datetime import timedelta

from fastapi.params import Depends
from pydantic import BaseModel

app = FastAPI()

config = AuthXConfig()
config.JWT_SECRET_KEY = "SECRET_KEY"

config.JWT_ACCESS_COOKIE_NAME = "access_token"
config.JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=30)

config.JWT_REFRESH_COOKIE_NAME = "refresh_token"
config.JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=5)

config.JWT_TOKEN_LOCATION = ["cookies"]

config.JWT_COOKIE_SECURE = False
config.JWT_COOKIE_HTTP_ONLY = True
config.JWT_COOKIE_SAMESITE = "lax"
config.JWT_COOKIE_CSRF_PROTECT=False

security = AuthX(config=config)

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_pwd = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_pwd.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


user_db = dict()


class UserLoginSchema(BaseModel):
    username: str
    password: str


class UserCreateSchema(BaseModel):
    username: str
    password: str


@app.get("/users")
def get_users():
    return user_db


@app.post("/register", status_code=201)
def register(user_data: UserCreateSchema):
    if user_data.username in user_db:
        raise HTTPException(status_code=400, detail="Username already registered")

    hashed_pwd = get_password_hash(user_data.password)
    user_db[user_data.username] = {
        "username": user_data.username,
        "password": hashed_pwd,
    }
    return {"msg": "User created!"}


@app.post("/login")
def login(creds: UserLoginSchema, response: Response):
    user = user_db.get(creds.username)
    if not user or not verify_password(creds.password, user["password"]):
        raise HTTPException(status_code=401, detail="Wrong username or password")

    access_token = security.create_access_token(uid=creds.username)
    refresh_token = security.create_refresh_token(uid=creds.username)

    security.set_access_cookies(access_token, response)
    security.set_refresh_cookies(refresh_token, response)

    return {"msg": "Login successful"}


@app.post("/refresh")
def refresh(response: Response, payload = Depends(security.refresh_token_required)):
    uid = payload.sub
    new_access_token = security.create_access_token(uid=uid)
    new_refresh_token = security.create_refresh_token(uid=uid)

    security.set_access_cookies(new_access_token, response)
    security.set_refresh_cookies(new_refresh_token, response)

    return {"msg": "Tokens refreshed"}


@app.get("/secret", dependencies=[Depends(security.access_token_required)])
def secret():
    return {"data": "TOP SECRET"}


@app.post("/logout")
def logout(response: Response):
    security.unset_access_cookies(response)
    security.unset_refresh_cookies(response)

    return {"msg": "Logged out"}
