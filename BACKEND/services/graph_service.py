"""
Microsoft Graph API Service for checking user group memberships
"""

import logging
import httpx
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from services.credential_provider import get_credential_provider

logger = logging.getLogger(__name__)


class GraphService:
    """Query Microsoft Graph API for user group memberships"""

    def __init__(self):
        """Initialize Graph Service with credential provider"""
        self.credential_provider = get_credential_provider()
        self._membership_cache = {}  # Cache user group checks
        self._cache_ttl_minutes = 10
        self.graph_api_url = "https://graph.microsoft.com/v1.0"

    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """Check if cache entry is still valid"""
        if not cache_entry:
            return False
        timestamp = cache_entry.get("timestamp")
        if not timestamp:
            return False
        age = datetime.now() - timestamp
        return age < timedelta(minutes=self._cache_ttl_minutes)

    async def is_user_in_group(self, user_id: str, group_id: str) -> bool:
        """
        Check if a user is a member of a specific Azure AD group

        Args:
            user_id: Azure AD user object ID
            group_id: Azure AD group object ID

        Returns:
            True if user is in group, False otherwise
        """
        cache_key = f"{user_id}:{group_id}"

        # Check cache first
        if cache_key in self._membership_cache:
            cached = self._membership_cache[cache_key]
            if self._is_cache_valid(cached):
                logger.debug(f"Group membership (cached): {user_id} in {group_id} = {cached['result']}")
                return cached["result"]

        try:
            # Get access token for Graph API
            credential = self.credential_provider.get_azure_credential()
            if not credential:
                logger.warning("No credential available for Graph API")
                return False

            # Get token for Graph API scope
            token = await self._get_graph_token(credential)
            if not token:
                logger.error("Failed to obtain Graph API token")
                return False

            # Call Graph API to check membership
            async with httpx.AsyncClient() as client:
                # Use the checkMemberObjects method for efficient group checking
                url = f"{self.graph_api_url}/me/memberOf"
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }

                response = await client.get(
                    url,
                    headers=headers,
                    timeout=10.0
                )

                if response.status_code == 200:
                    member_of = response.json().get("value", [])
                    is_member = any(item.get("id") == group_id for item in member_of)

                    # Cache the result
                    self._membership_cache[cache_key] = {
                        "result": is_member,
                        "timestamp": datetime.now()
                    }

                    logger.debug(f"Group membership check: {user_id} in {group_id} = {is_member}")
                    return is_member
                else:
                    logger.warning(f"Graph API error ({response.status_code}): {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error checking group membership: {str(e)}")
            return False

    async def _get_graph_token(self, credential) -> Optional[str]:
        """
        Get an access token for Microsoft Graph API

        Args:
            credential: Azure credential object

        Returns:
            Access token string or None if failed
        """
        try:
            # For service principal/managed identity credentials
            scopes = ["https://graph.microsoft.com/.default"]
            token_result = await asyncio.to_thread(credential.get_token, scopes[0])
            return token_result.token
        except Exception as e:
            logger.error(f"Failed to get Graph API token: {str(e)}")
            return None

    def clear_cache(self):
        """Clear the membership cache (useful for testing or forced refresh)"""
        self._membership_cache.clear()
        logger.debug("Membership cache cleared")


# Singleton instance
_graph_service = None


def get_graph_service() -> GraphService:
    """Get or create the singleton GraphService instance"""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
