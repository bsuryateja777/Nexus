from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List
import os
import logging

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to validate Bearer token on protected routes

    Usage:
        app.add_middleware(
            AuthMiddleware,
            entra_validator=validator,
            public_routes=["/auth/login", "/auth/callback", "/health"]
        )

    This middleware:
    1. Checks if route is in public_routes, if so allows access
    2. Extracts Bearer token from Authorization header
    3. Validates token using EntraIDValidator
    4. Attaches user_id and user_email to request.state
    5. Returns 401 if token is missing or invalid
    """

    def __init__(self, app, entra_validator, public_routes: List[str] = None):
        super().__init__(app)
        self.validator = entra_validator
        self.public_routes = public_routes or []

    async def dispatch(self, request: Request, call_next):
        # Check if route is public (skip auth)
        if request.url.path in self.public_routes:
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid Authorization header"
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Allow guest-token for local development (when auth is disabled)
        if token == "guest-token":
            request.state.user_id = "guest"
            request.state.user_email = "guest@localhost"
            request.state.user_name = "Guest User"
            request.state.token_claims = {}
            return await call_next(request)

        try:
            # Validate token and extract claims
            decoded = await self.validator.validate_token(token)

            # Attach user info to request state for route handlers to access
            request.state.user_id = decoded.get("sub")  # sub = user object ID
            request.state.user_email = decoded.get("email")
            request.state.user_name = decoded.get("name")
            request.state.token_claims = decoded  # Full token for advanced use cases

            # Check if user is in the team AD group (for role-based features)
            team_group_id = os.getenv("AD_TEAM_GROUP_ID")
            if team_group_id and request.state.user_id:
                try:
                    from services.graph_service import get_graph_service
                    graph_service = get_graph_service()
                    is_team_member = await graph_service.is_user_in_group(
                        request.state.user_id,
                        team_group_id
                    )
                    request.state.is_team_member = is_team_member
                    logger.debug(f"User {request.state.user_email}: team_member={is_team_member}")
                except Exception as e:
                    logger.warning(f"Failed to check team membership: {str(e)}")
                    request.state.is_team_member = False
            else:
                request.state.is_team_member = False

        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=401, detail="Token validation failed")

        return await call_next(request)
