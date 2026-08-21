from fastapi import APIRouter, status

from agent_hub.auth import AuthenticatedUser
from agent_hub.dependencies import BearerCredentials, CurrentUser, auth_service
from agent_hub.schemas import AuthResponse, Credentials, User

router = APIRouter(prefix="/auth", tags=["authentication"])


def response(user: AuthenticatedUser, token: str) -> AuthResponse:
    return AuthResponse(
        token=token, user=User(id=user.id, email=user.email, role=user.role)
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: Credentials) -> AuthResponse:
    user, token = auth_service.register(str(body.email), body.password)
    return response(user, token)


@router.post("/login", response_model=AuthResponse)
def login(body: Credentials) -> AuthResponse:
    user, token = auth_service.login(str(body.email), body.password)
    return response(user, token)


@router.get("/me", response_model=User)
def me(user: CurrentUser) -> User:
    return User(id=user.id, email=user.email, role=user.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: BearerCredentials, user: CurrentUser) -> None:
    auth_service.logout(credentials.credentials)
