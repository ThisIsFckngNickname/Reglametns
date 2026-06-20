from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        if not v or len(v) > 255:
            raise ValueError("Email must be between 1 and 255 characters")
        pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


class RegisterResponse(BaseModel):
    message: str
    code_length: int = 6


class VerifyRegistrationRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError("Code must be exactly 6 digits")
        return v


class VerifyResponse(BaseModel):
    message: str
    verified: bool


class LoginRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        if not v or len(v) > 255:
            raise ValueError("Email must be between 1 and 255 characters")
        pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LoginResponse(BaseModel):
    message: str


class VerifyLoginRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v or len(v) != 6 or not v.isdigit():
            raise ValueError("Code must be exactly 6 digits")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 900


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 900


class LogoutResponse(BaseModel):
    message: str
