import os
import json
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
import jwt
from jwt import PyJWT


class EntraIDValidator:
    """Validate JWT tokens from Azure Entra ID"""

    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.jwks_uri = f"{self.authority}/discovery/v2.0/keys"
        self._cached_keys = None
        self._cache_time = None

    async def validate_token(self, token: str) -> dict:
        """
        Validate token:
        1. Verify signature using Entra ID public keys
        2. Check expiry (exp claim)
        3. Verify aud claim matches client_id
        4. Return decoded token (includes sub = user_id, oid, email, name, etc.)
        """
        try:
            # First, decode without verification to get the header
            unverified = jwt.decode(token, options={"verify_signature": False})

            # Fetch public keys from Entra ID
            keys = await self._get_jwks()

            # Find the correct key based on kid in token header
            token_header = jwt.get_unverified_header(token)
            kid = token_header.get("kid")

            # Find matching key
            key_data = None
            for key in keys:
                if key.get("kid") == kid:
                    key_data = key
                    break

            if not key_data:
                raise ValueError(f"Key {kid} not found in Entra ID JWKS")

            # Convert JWKS to RSA public key
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(json.dumps(key_data))

            # Decode and verify JWT
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_exp": True}
            )

            return decoded  # {sub, oid, email, name, ...}

        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")

    async def _get_jwks(self):
        """Fetch JWKS from Entra ID (cached for 24 hours)"""
        # Check if cache is still valid (24 hours)
        if self._cached_keys and self._cache_time:
            cache_age = (datetime.now() - self._cache_time).total_seconds()
            if cache_age < 86400:  # 24 hours
                return self._cached_keys

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.jwks_uri, timeout=10)
                resp.raise_for_status()

                self._cached_keys = resp.json()["keys"]
                self._cache_time = datetime.now()

                return self._cached_keys
        except httpx.RequestError as e:
            raise ValueError(f"Failed to fetch JWKS from Entra ID: {str(e)}")


class AuthService:
    """Manage Azure Entra ID OAuth2 flow"""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.token_endpoint = f"{self.authority}/oauth2/v2.0/token"
        self.authorize_endpoint = f"{self.authority}/oauth2/v2.0/authorize"
        self.validator = EntraIDValidator(tenant_id, client_id)

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """
        Generate Azure Entra ID login URL

        Args:
            redirect_uri: URL to redirect to after login
            state: CSRF protection token

        Returns:
            Full authorization URL
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid profile email offline_access",
            "redirect_uri": redirect_uri,
            "response_mode": "query",
            "state": state
        }

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.authorize_endpoint}?{query_string}"

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access/refresh tokens

        Args:
            code: Authorization code from Entra ID callback
            redirect_uri: Must match the redirect_uri used in authorization request

        Returns:
            Dictionary with access_token, id_token, refresh_token, expires_in
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                        "scope": "openid profile email offline_access"
                    },
                    timeout=10
                )
                response.raise_for_status()

                return response.json()

        except httpx.RequestError as e:
            raise ValueError(f"Failed to exchange code for token: {str(e)}")
        except httpx.HTTPStatusError as e:
            error_data = e.response.json()
            raise ValueError(f"Token exchange failed: {error_data.get('error_description', str(e))}")

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token using a refresh token

        Args:
            refresh_token: Refresh token from previous authorization

        Returns:
            Dictionary with new access_token and updated expires_in
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                        "scope": "openid profile email offline_access"
                    },
                    timeout=10
                )
                response.raise_for_status()

                return response.json()

        except httpx.RequestError as e:
            raise ValueError(f"Failed to refresh token: {str(e)}")
