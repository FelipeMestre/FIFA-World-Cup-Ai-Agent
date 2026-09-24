from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str = Field(min_length=1, max_length=128)
    is_admin: bool
