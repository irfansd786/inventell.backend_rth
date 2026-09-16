from pydantic import BaseModel, EmailStr


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = 'STAFF'


class LoginJsonIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str | None = None


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    store: str

    model_config = {'from_attributes': True}
