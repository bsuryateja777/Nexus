"""
Centralized credential management using Azure DefaultAzureCredential
Supports both UAMI (User Assigned Managed Identity) and local fallback to environment variables
"""

import logging
import os
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)


class CredentialProvider:
    """
    Centralized credential provider that uses Azure DefaultAzureCredential
    with fallback to environment variables for local development.

    Priority order for credentials:
    1. Azure DefaultAzureCredential (UAMI, managed identity, az login, etc.)
    2. Environment variables (for local development)
    3. Key Vault (if available)
    """

    _instance = None
    _azure_credential = None
    _secret_client = None
    _anthropic_key_cache = None

    def __new__(cls):
        """Singleton pattern to ensure only one instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize credential provider"""
        if not self._azure_credential:
            try:
                self._azure_credential = DefaultAzureCredential()
                # Log which identity is being used
                self._log_credential_source()
            except Exception as e:
                logger.warning(f"Failed to initialize DefaultAzureCredential: {e}")
                self._azure_credential = None

    def _log_credential_source(self):
        """Log which credential source is being used"""
        try:
            import os
            from azure.identity import ClientSecretCredential

            # Check for service principal environment variables
            client_id = os.getenv("AZURE_CLIENT_ID")
            tenant_id = os.getenv("AZURE_TENANT_ID")

            if client_id and tenant_id:
                logger.info(f"✓ Using Service Principal (Client ID: {client_id[:8]}...)")
            else:
                logger.info("✓ Using Azure CLI / Managed Identity credential chain")
        except Exception as e:
            logger.debug(f"Could not determine credential source: {e}")

    def get_azure_credential(self):
        """
        Get DefaultAzureCredential instance for use with Azure SDKs.

        Returns:
            DefaultAzureCredential instance or None if unavailable
        """
        return self._azure_credential

    def _get_secret_client(self) -> Optional[SecretClient]:
        """
        Lazy-initialize Key Vault Secret Client

        Returns:
            SecretClient instance or None if Key Vault not configured
        """
        if self._secret_client is None:
            key_vault_url = os.getenv("AZURE_KEY_VAULT_URL")
            if not key_vault_url:
                logger.debug("AZURE_KEY_VAULT_URL not set; Key Vault operations will be skipped")
                return None

            try:
                if not self._azure_credential:
                    logger.warning("Azure credential not available; cannot connect to Key Vault")
                    return None

                self._secret_client = SecretClient(vault_url=key_vault_url, credential=self._azure_credential)
                logger.debug(f"Key Vault client initialized: {key_vault_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize Key Vault client: {e}")
                return None

        return self._secret_client

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve a secret from Azure Key Vault.

        Args:
            secret_name: Name of the secret to retrieve

        Returns:
            Secret value as string, or None if not found or Key Vault unavailable
        """
        secret_client = self._get_secret_client()
        if not secret_client:
            logger.debug(f"Key Vault not available; secret '{secret_name}' cannot be retrieved")
            return None

        try:
            secret = secret_client.get_secret(secret_name)
            logger.debug(f"Secret retrieved from Key Vault: {secret_name}")
            return secret.value
        except Exception as e:
            logger.debug(f"Failed to retrieve secret '{secret_name}' from Key Vault: {e}")
            return None

    def get_anthropic_key(self) -> str:
        """
        Retrieve Anthropic API key from Key Vault (primary) or environment variable (fallback).

        Priority:
        1. Azure Key Vault (if available)
        2. ANTHROPIC_API_KEY environment variable

        Returns:
            Anthropic API key as string

        Raises:
            ValueError: If no Anthropic key can be found
        """
        # Return cached key if available
        if self._anthropic_key_cache:
            return self._anthropic_key_cache

        # Try to get from Key Vault first
        try:
            key = self.get_secret("CLAUDE-API-KEY")
            if key:
                self._anthropic_key_cache = key
                logger.debug("Anthropic API key retrieved from Key Vault")
                return key
        except Exception as e:
            logger.debug(f"Could not retrieve Anthropic key from Key Vault: {e}")

        # Fallback to environment variable
        key = os.getenv("ANTHROPIC_API_KEY")
        if key:
            self._anthropic_key_cache = key
            logger.debug("Anthropic API key retrieved from environment variable")
            return key

        # No key found
        raise ValueError(
            "Anthropic API key not found. "
            "Set AZURE_KEY_VAULT_URL and ensure CLAUDE-API-KEY exists in Key Vault, "
            "or set ANTHROPIC_API_KEY environment variable"
        )

    def get_storage_account_url(self) -> str:
        """
        Construct Azure Storage account URL from environment config.

        Returns:
            Storage account URL (e.g., https://storageaccount.blob.core.windows.net)

        Raises:
            ValueError: If storage account name not configured
        """
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        if not account_name:
            raise ValueError(
                "AZURE_STORAGE_ACCOUNT_NAME not configured. "
                "Required for DefaultAzureCredential authentication."
            )

        return f"https://{account_name}.blob.core.windows.net"

    def get_document_intelligence_endpoint(self) -> str:
        """
        Get Document Intelligence endpoint from environment.

        Returns:
            Document Intelligence endpoint URL

        Raises:
            ValueError: If endpoint not configured
        """
        endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not configured")
        return endpoint

    def get_cognitive_search_endpoint(self) -> str:
        """
        Construct Cognitive Search endpoint from service name.

        Returns:
            Cognitive Search endpoint URL

        Raises:
            ValueError: If service name not configured
        """
        service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
        if not service_name:
            raise ValueError("AZURE_SEARCH_SERVICE_NAME not configured")
        return f"https://{service_name}.search.windows.net"

    def get_entra_client_secret(self) -> Optional[str]:
        """
        Retrieve Entra ID Client Secret from Key Vault (primary) or environment variable (fallback).

        Priority:
        1. Azure Key Vault secret 'ENTRA-CLIENT-SECRET'
        2. ENTRA_CLIENT_SECRET environment variable

        Returns:
            Entra ID Client Secret as string, or None if not found
        """
        # Try Key Vault first
        try:
            secret = self.get_secret("ENTRA-CLIENT-SECRET")
            if secret:
                logger.debug("Entra ID client secret retrieved from Key Vault")
                return secret
        except Exception as e:
            logger.debug(f"Could not retrieve Entra secret from Key Vault: {e}")

        # Fallback to environment variable
        secret = os.getenv("ENTRA_CLIENT_SECRET")
        if secret:
            logger.debug("Entra ID client secret retrieved from environment variable")
            return secret

        return None

    def get_entra_client_id(self) -> Optional[str]:
        """
        Retrieve Entra ID Client ID from Key Vault (primary) or environment variable (fallback).

        Returns:
            Entra ID Client ID as string, or None if not found
        """
        # Try Key Vault first
        try:
            secret = self.get_secret("ENTRA-CLIENT-ID")
            if secret:
                logger.debug("Entra ID client ID retrieved from Key Vault")
                return secret
        except Exception as e:
            logger.debug(f"Could not retrieve Entra Client ID from Key Vault: {e}")

        # Fallback to environment variable
        client_id = os.getenv("ENTRA_CLIENT_ID")
        if client_id:
            logger.debug("Entra ID client ID retrieved from environment variable")
            return client_id

        return None

    def get_entra_tenant_id(self) -> Optional[str]:
        """
        Retrieve Entra ID Tenant ID from Key Vault (primary) or environment variable (fallback).

        Returns:
            Entra ID Tenant ID as string, or None if not found
        """
        # Try Key Vault first
        try:
            secret = self.get_secret("ENTRA-TENANT-ID")
            if secret:
                logger.debug("Entra ID tenant ID retrieved from Key Vault")
                return secret
        except Exception as e:
            logger.debug(f"Could not retrieve Entra Tenant ID from Key Vault: {e}")

        # Fallback to environment variable
        tenant_id = os.getenv("ENTRA_TENANT_ID")
        if tenant_id:
            logger.debug("Entra ID tenant ID retrieved from environment variable")
            return tenant_id

        return None

    def get_database_url_entra(self, base_url: str) -> str:
        """
        Convert PostgreSQL connection string to Entra ID token-based authentication.

        For Azure Database for PostgreSQL Flexible Server, replace password with
        an Entra ID token that gets refreshed before expiry.

        Args:
            base_url: Base PostgreSQL connection string (e.g., postgresql://user@host/db)

        Returns:
            Modified connection string with token as password
        """
        # This will be implemented in database.py with token refresh logic
        # Placeholder for now
        return base_url


def get_credential_provider() -> CredentialProvider:
    """
    Get the singleton CredentialProvider instance.

    Returns:
        CredentialProvider instance
    """
    return CredentialProvider()
