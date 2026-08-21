from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent_hub.auth import AuthService, AuthenticatedUser
from agent_hub.chat import ChatService
from agent_hub.database import load_database

database = load_database()
auth_service = AuthService(database)
service = ChatService(database=database)
bearer = HTTPBearer(auto_error=False)


def get_service() -> ChatService:
    return service


Service = Annotated[ChatService, Depends(get_service)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        from fastapi import HTTPException, status

        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_service.authenticate(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer)]


def get_admin_user(user: CurrentUser) -> AuthenticatedUser:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


AdminUser = Annotated[AuthenticatedUser, Depends(get_admin_user)]
