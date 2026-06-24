"""
Azure Blob Storage Service for knowledge base document management
"""

import logging
import os
from typing import List, Dict, Optional, Any
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.data.tables import TableClient
from azure.core.credentials import AzureKeyCredential
from services.credential_provider import get_credential_provider

logger = logging.getLogger(__name__)


class AzureStorageService:
    """Manage knowledge base documents in Azure Blob Storage"""

    def __init__(self, connection_string: Optional[str] = None, credential=None):
        """
        Initialize Azure Storage Service

        Args:
            connection_string: Azure Storage connection string (from .env if not provided)
            credential: Azure credential object (DefaultAzureCredential if not provided)
        """
        self.connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_service_client = None
        self.table_client = None
        self.credential_provider = get_credential_provider()

        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                logger.info("✓ Azure Storage Service initialized (connection string)")
            except Exception as e:
                logger.error(f"Failed to initialize Azure Storage with connection string: {str(e)}")
                self.blob_service_client = None
        else:
            try:
                account_url = self.credential_provider.get_storage_account_url()
                azure_credential = credential or self.credential_provider.get_azure_credential()

                if not azure_credential:
                    logger.warning("No Azure credential available for Storage Service")
                    return

                self.blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=azure_credential
                )
                logger.info("✓ Azure Storage Service initialized (managed identity)")
            except Exception as e:
                logger.error(f"Failed to initialize Azure Storage with managed identity: {str(e)}")
                self.blob_service_client = None

    def is_configured(self) -> bool:
        """Check if Azure Storage is properly configured"""
        return self.blob_service_client is not None

    async def list_containers(self) -> List[str]:
        """
        List all containers in the storage account

        Returns:
            List of container names
        """
        if not self.is_configured():
            logger.warning("Azure Storage not configured")
            return []

        try:
            containers = []
            for container in self.blob_service_client.list_containers():
                containers.append(container.name)
            logger.info(f"Found {len(containers)} containers")
            return containers
        except Exception as e:
            logger.error(f"Failed to list containers: {str(e)}")
            return []

    async def list_documents(self, service_id: str) -> List[Dict[str, Any]]:
        """
        List all documents in a service container

        Args:
            service_id: Service container name (e.g., "ai-attack")

        Returns:
            List of document metadata
        """
        if not self.is_configured():
            return []

        try:
            container_client = self.blob_service_client.get_container_client(service_id)

            documents = []
            for blob in container_client.list_blobs():
                documents.append({
                    "name": blob.name,
                    "size": blob.size,
                    "created": blob.creation_time.isoformat() if blob.creation_time else None,
                    "modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "content_type": blob.content_settings.content_type,
                    "service_id": service_id,
                    "uri": f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{service_id}/{blob.name}"
                })

            logger.info(f"Found {len(documents)} documents in {service_id}")
            return documents

        except Exception as e:
            logger.error(f"Failed to list documents in {service_id}: {str(e)}")
            return []

    async def get_document_url(self, service_id: str, document_name: str) -> Optional[str]:
        """
        Get the public URL for a document (requires SAS token for private containers)

        Args:
            service_id: Service container name
            document_name: Document blob name

        Returns:
            URL to the document
        """
        if not self.is_configured():
            return None

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=service_id,
                blob=document_name
            )
            # Return the full URI (requires authentication)
            uri = blob_client.url
            logger.info(f"Generated URI for {service_id}/{document_name}")
            return uri
        except Exception as e:
            logger.error(f"Failed to get document URL: {str(e)}")
            return None

    async def download_document(self, service_id: str, document_name: str) -> Optional[bytes]:
        """
        Download document content from Blob Storage

        Args:
            service_id: Service container name
            document_name: Document blob name

        Returns:
            Document content as bytes, or None if failed
        """
        if not self.is_configured():
            return None

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=service_id,
                blob=document_name
            )
            download_stream = blob_client.download_blob()
            content = download_stream.readall()
            logger.info(f"Downloaded {len(content)} bytes from {service_id}/{document_name}")
            return content
        except Exception as e:
            logger.error(f"Failed to download document: {str(e)}")
            return None

    async def upload_document(
        self,
        service_id: str,
        document_name: str,
        content: bytes,
        overwrite: bool = True
    ) -> bool:
        """
        Upload a document to Blob Storage

        Args:
            service_id: Service container name
            document_name: Document blob name
            content: Document content as bytes
            overwrite: Whether to overwrite if exists

        Returns:
            True if successful
        """
        if not self.is_configured():
            return False

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=service_id,
                blob=document_name
            )
            blob_client.upload_blob(content, overwrite=overwrite)
            logger.info(f"Uploaded {document_name} to {service_id} ({len(content)} bytes)")
            return True
        except Exception as e:
            logger.error(f"Failed to upload document: {str(e)}")
            return False

    async def delete_document(self, service_id: str, document_name: str) -> bool:
        """
        Delete a document from Blob Storage

        Args:
            service_id: Service container name
            document_name: Document blob name

        Returns:
            True if successful
        """
        if not self.is_configured():
            return False

        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=service_id,
                blob=document_name
            )
            blob_client.delete_blob()
            logger.info(f"Deleted {document_name} from {service_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {str(e)}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "configured": self.is_configured(),
            "account_name": self.blob_service_client.account_name if self.is_configured() else None,
        }

    def _get_table_client(self, table_name: str = "servicelinks") -> Optional[TableClient]:
        """
        Lazy-initialize and return a TableClient for the specified table

        Args:
            table_name: Azure Table Storage table name

        Returns:
            TableClient instance or None if cannot be initialized
        """
        if not self.is_configured():
            logger.warning("Blob Storage not configured, cannot initialize Table Storage")
            return None

        try:
            if self.connection_string:
                client = TableClient.from_connection_string(
                    self.connection_string,
                    table_name=table_name
                )
            else:
                account_url = self.credential_provider.get_storage_account_url()
                azure_credential = self.credential_provider.get_azure_credential()

                if not azure_credential:
                    logger.warning("No credential for Table Storage")
                    return None

                table_url = f"{account_url}/Tables('{table_name}')"
                client = TableClient(
                    account_url=account_url,
                    table_name=table_name,
                    credential=azure_credential
                )

            return client
        except Exception as e:
            logger.error(f"Failed to initialize Table Client for '{table_name}': {str(e)}")
            return None

    async def get_servicelinks(
        self,
        search_query: str,
        service_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query the servicelinks table for relevant documentation links

        Args:
            search_query: The search query to find relevant links for
            service_id: Optional service ID to filter by (e.g., "ai-attack")

        Returns:
            List of servicelink entries with title, url, description
        """
        try:
            table_client = self._get_table_client("ServiceLinks")
            if not table_client:
                logger.error("Table Storage not available for ServiceLinks")
                return []

            # Query servicelinks table
            # Partition key is typically service_id, row key might be search_term or category
            # Note: Normalize service_id to match table format (spaces instead of hyphens, title case)
            if service_id:
                # Convert "ai-attack" to "AI attack" format for table lookup
                normalized_service_id = service_id.replace("-", " ").title()
                query_filter = f"PartitionKey eq '{normalized_service_id}'"
                logger.info(f"ServiceLinks query: service_id={service_id} -> filter={query_filter}")
            else:
                # No filter - get all applicable links
                query_filter = None
                logger.info("ServiceLinks query: fetching all links (no service filter)")

            links = []
            try:
                if query_filter:
                    entities = table_client.query_entities(filter=query_filter)
                else:
                    entities = table_client.query_entities()

                for entity in entities:
                    # Extract standard link properties from table entity
                    link_entry = {
                        "title": entity.get("title", entity.get("RowKey", "Untitled")),
                        "url": entity.get("url", ""),
                        "description": entity.get("description", ""),
                        "category": entity.get("category", ""),
                        "service": entity.get("PartitionKey", service_id or "")
                    }

                    # Skip entries without URL
                    if not link_entry["url"]:
                        continue

                    # Filter by search relevance if needed (simple keyword matching)
                    if search_query:
                        search_lower = search_query.lower()
                        title_match = search_lower in link_entry["title"].lower()
                        desc_match = search_lower in link_entry["description"].lower()
                        if title_match or desc_match:
                            links.append(link_entry)
                    else:
                        # No search query filter, include all links
                        links.append(link_entry)

                logger.info(f"Found {len(links)} servicelinks for query='{search_query}' service='{service_id}'")
                return links

            except Exception as e:
                logger.error(f"Error querying servicelinks table: {str(e)}")
                return []

        except Exception as e:
            logger.error(f"Failed to get servicelinks: {str(e)}")
            return []
