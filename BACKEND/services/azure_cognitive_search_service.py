"""
Azure Cognitive Search Service for indexing and searching documents
"""

import logging
import os
import json
from typing import Optional, Dict, List, Any
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    SimpleField, SearchableField
)
from azure.core.credentials import AzureKeyCredential
from services.credential_provider import get_credential_provider

logger = logging.getLogger(__name__)


class AzureCognitiveSearchService:
    """Index and search knowledge base documents using Azure Cognitive Search"""

    def __init__(
        self,
        service_name: Optional[str] = None,
        admin_key: Optional[str] = None,
        index_name: Optional[str] = None,
        credential=None
    ):
        """
        Initialize Cognitive Search Service

        Args:
            service_name: Search service name (from .env if not provided)
            admin_key: Admin key (from .env if not provided)
            index_name: Index name to use (from AZURE_SEARCH_INDEX_NAME env if not provided)
            credential: Azure credential object (DefaultAzureCredential if not provided)
        """
        self.service_name = service_name or os.getenv("AZURE_SEARCH_SERVICE_NAME")
        self.admin_key = admin_key or os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.index_name = index_name or os.getenv("AZURE_SEARCH_INDEX_NAME", "ai-attack")
        self.endpoint = f"https://{self.service_name}.search.windows.net" if self.service_name else None
        self.credential_provider = get_credential_provider()
        self.index_client = None
        self.search_client = None
        self.credential = None
        self.custom_search_clients = {}  # Cache for custom index clients

        if not self.endpoint:
            logger.warning("Cognitive Search service name not configured")
            return

        try:
            if self.admin_key:
                credentials = AzureKeyCredential(self.admin_key)
                logger.debug("Using admin key for Cognitive Search")
            else:
                credentials = credential or self.credential_provider.get_azure_credential()
                if not credentials:
                    logger.error("No credentials available for Cognitive Search")
                    return
                logger.debug("Using managed identity for Cognitive Search")

            self.credential = credentials
            self.index_client = SearchIndexClient(endpoint=self.endpoint, credential=credentials)
            self.search_client = SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=credentials)
            logger.info(f"✓ Cognitive Search initialized: {self.service_name} (index: {self.index_name})")
        except Exception as e:
            logger.error(f"Cognitive Search initialization failed: {str(e)}")
            self.index_client = None
            self.search_client = None

    def is_configured(self) -> bool:
        """Check if Cognitive Search is properly configured"""
        return self.search_client is not None

    def _get_search_client_for_index(self, index_name: str) -> Optional[SearchClient]:
        """
        Get or create a SearchClient for a specific index with caching

        Args:
            index_name: Name of the index

        Returns:
            SearchClient for the index, or None if creation fails
        """
        if not self.endpoint or not self.credential:
            logger.debug(f"Cannot create SearchClient for {index_name}: endpoint or credential missing")
            return None

        # Return cached client if available
        if index_name in self.custom_search_clients:
            logger.debug(f"Using cached SearchClient for index: {index_name}")
            return self.custom_search_clients[index_name]

        # Use default client if same index
        if index_name == self.index_name:
            logger.debug(f"Using default search_client for index: {index_name}")
            return self.search_client

        # Create new client for custom index
        try:
            logger.info(f"🔍 Creating SearchClient for custom index: {index_name}")
            client = SearchClient(endpoint=self.endpoint, index_name=index_name, credential=self.credential)
            self.custom_search_clients[index_name] = client
            logger.info(f"✓ SearchClient created and cached for index: {index_name}")
            return client
        except Exception as e:
            logger.error(f"❌ Failed to create SearchClient for index {index_name}: {type(e).__name__}: {str(e)}")
            return None

    def _create_index(self, recreate: bool = False) -> bool:
        """
        Create search index if it doesn't exist

        Args:
            recreate: If True, delete and recreate the index

        Returns:
            True if successful or index already exists
        """
        if not self.index_client:
            return False

        try:
            # Check if index exists
            try:
                if recreate:
                    raise Exception("Force recreate")
                self.index_client.get_index(self.index_name)
                logger.debug(f"Index '{self.index_name}' already exists")
                return True
            except Exception:
                # Index doesn't exist or force recreate, create it
                if recreate:
                    try:
                        logger.debug(f"Deleting old index: {self.index_name}")
                        self.index_client.delete_index(self.index_name)
                    except Exception as e:
                        logger.debug(f"Could not delete index (may not exist): {str(e)}")
                pass

            # Define index schema
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="service_id", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="document_name", type=SearchFieldDataType.String),
                SearchableField(name="document_path", type=SearchFieldDataType.String),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="file_size", type=SearchFieldDataType.Int32),
                SimpleField(name="created_date", type=SearchFieldDataType.DateTimeOffset),
                SimpleField(name="modified_date", type=SearchFieldDataType.DateTimeOffset),
                SimpleField(name="content_type", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="document_uri", type=SearchFieldDataType.String),
                SimpleField(name="images_metadata", type=SearchFieldDataType.String),
                SimpleField(name="has_visual_content", type=SearchFieldDataType.Boolean, filterable=True),
            ]

            index = SearchIndex(name=self.index_name, fields=fields)
            self.index_client.create_index(index)
            logger.debug(f"Created index: {self.index_name}")
            return True

        except Exception as e:
            logger.error(f"Index creation failed: {str(e)}")
            return False

    async def index_document(
        self,
        document_id: str,
        service_id: str,
        document_name: str,
        document_path: str,
        title: str,
        content: str,
        file_size: int = 0,
        created_date: Optional[str] = None,
        modified_date: Optional[str] = None,
        content_type: str = "text/plain",
        document_uri: str = "",
        images_metadata: Optional[List[Dict[str, Any]]] = None,
        has_visual_content: bool = False
    ) -> bool:
        """
        Index a single document

        Args:
            document_id: Unique document ID
            service_id: Service container name (e.g., "ai-attack")
            document_name: Original document name
            document_path: Path in blob storage
            title: Document title
            content: Extracted text content
            file_size: File size in bytes
            created_date: ISO format creation date
            modified_date: ISO format modification date
            content_type: MIME type
            document_uri: Full URI to blob
            images_metadata: List of image metadata dicts
            has_visual_content: Whether document contains images

        Returns:
            True if successful
        """
        if not self.search_client:
            logger.error(f"[INDEX] search_client is None")
            return False

        try:
            # Convert images metadata to JSON string for storage
            images_json = ""
            if images_metadata:
                import json
                images_json = json.dumps(images_metadata)

            document = {
                "id": document_id,
                "service_id": service_id,
                "document_name": document_name,
                "document_path": document_path,
                "title": title,
                "content": content[:100000],  # Limit content to avoid indexing errors
                "file_size": file_size,
                "created_date": created_date,
                "modified_date": modified_date,
                "content_type": content_type,
                "document_uri": document_uri,
                "images_metadata": images_json,
                "has_visual_content": has_visual_content,
            }

            self.search_client.upload_documents(documents=[document])
            logger.debug(f"Indexed: {document_name} (ID: {document_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to index {document_id}: {str(e)}")
            return False

    async def batch_index_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> int:
        """
        Index multiple documents in a batch

        Args:
            documents: List of document dictionaries

        Returns:
            Number of successfully indexed documents
        """
        if not self.search_client:
            return 0

        try:
            self.search_client.upload_documents(documents=documents)
            logger.debug(f"Batch indexed {len(documents)} documents")
            return len(documents)

        except Exception as e:
            logger.error(f"Batch indexing failed: {str(e)}")
            return 0

    async def search(
        self,
        query: str,
        service_id: Optional[str] = None,
        top_k: int = 5,
        include_score: bool = True,
        use_semantic_search: bool = True,
        index_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search documents in the index with optional semantic ranking

        Args:
            query: Search query
            service_id: Optional service filter (only applied if index has service_id field)
            top_k: Number of results
            include_score: Include relevance scores
            use_semantic_search: Use semantic ranking for better RAG results
            index_name: Optional custom index name (defaults to configured index)

        Returns:
            List of search results
        """
        if not self.search_client:
            return []

        try:
            # Use custom index if provided, otherwise use default
            search_idx_name = index_name or self.index_name or os.getenv("AZURE_SEARCH_INDEX_NAME")

            # Get search client for the specified index
            if index_name and index_name != self.index_name:
                search_client = self._get_search_client_for_index(index_name)
                if not search_client:
                    logger.warning(f"Failed to get SearchClient for custom index {index_name}, using default")
                    search_client = self.search_client
            else:
                search_client = self.search_client

            # Build filter if service_id provided
            # Note: Only use service_id filter if index actually has this field
            filter_expr = None

            # Skip service_id filter for RAG indexes (they don't have this field)
            if service_id and "rag" not in (search_idx_name or "").lower():
                filter_expr = f"service_id eq '{service_id}'"

            # Get semantic configuration name from environment
            semantic_config = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIG")

            # Execute search with semantic ranking if available
            try:
                logger.debug(f"Executing search: query='{query}', index='{search_idx_name}', semantic={use_semantic_search and bool(semantic_config)}, top_k={top_k}")

                search_kwargs = {
                    "search_text": query,
                    "filter": filter_expr,
                    "top": top_k,
                    "include_total_count": True,
                }

                # Add semantic ranking if configured
                if use_semantic_search and semantic_config:
                    search_kwargs["query_type"] = "semantic"
                    search_kwargs["semantic_configuration_name"] = semantic_config

                results = search_client.search(**search_kwargs)
                result_list = list(results)
                logger.debug(f"Search returned {len(result_list)} results (total_count: {results.get_count() if hasattr(results, 'get_count') else 'unknown'})")
                # Re-iterate since we consumed the list
                results = iter(result_list)
            except Exception as e:
                logger.error(f"Search error on first attempt: {type(e).__name__}: {str(e)}")
                # If semantic search fails, fallback to keyword search
                if use_semantic_search and semantic_config and "semantic" in str(e).lower():
                    logger.debug("Semantic search failed, falling back to keyword search")
                    results = self.search_client.search(
                        search_text=query,
                        filter=filter_expr,
                        top=top_k,
                        include_total_count=True,
                    )
                    result_list = list(results)
                    logger.debug(f"Fallback search returned {len(result_list)} results")
                    results = iter(result_list)
                # If filter fails (field might not exist), retry without filter
                elif filter_expr and ("service_id" in str(e) or "property" in str(e).lower()):
                    logger.debug(f"Filter not available, retrying without filter")
                    results = self.search_client.search(
                        search_text=query,
                        filter=None,
                        top=top_k,
                        include_total_count=True,
                    )
                    result_list = list(results)
                    logger.debug(f"Search retry returned {len(result_list)} results")
                    results = iter(result_list)
                else:
                    raise

            search_results = []
            for result in results:
                # Support multiple field naming conventions
                content = result.get("content_text") or result.get("content") or result.get("chunk", "")
                title = result.get("document_title") or result.get("title") or result.get("document_name", "Unknown")

                search_results.append({
                    "id": result.get("id") or result.get("chunk_id", "unknown"),
                    "service_id": result.get("service_id"),
                    "title": title,
                    "document_name": result.get("document_name"),
                    "content": content[:2000],
                    "full_content": content,
                    "score": result.get("@search.score", 0),
                    "semantic_score": result.get("@search.reranker_score", None),  # Semantic ranking score
                    "document_uri": result.get("document_uri"),
                    "content_type": result.get("content_type"),
                    "images_metadata": result.get("images_metadata", ""),
                    "has_visual_content": result.get("has_visual_content", False),
                })

            logger.debug(f"Search '{query}': {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return []

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the index

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful
        """
        if not self.search_client:
            return False

        try:
            self.search_client.delete_documents(documents=[{"id": document_id}])
            logger.debug(f"Deleted document: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed: {str(e)}")
            return False

    async def clear_index(self) -> bool:
        """
        Delete all documents from the index

        Args:
            Confirm: True to proceed with deletion

        Returns:
            True if successful
        """
        if not self.search_client:
            return False

        try:
            results = self.search_client.search(search_text="*", top=10000)
            doc_ids = [{"id": result["id"]} for result in results]

            if doc_ids:
                self.search_client.delete_documents(documents=doc_ids)
                logger.info(f"Cleared {len(doc_ids)} documents from index")

            return True
        except Exception as e:
            logger.error(f"Clear index failed: {str(e)}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "configured": self.is_configured(),
            "service_name": self.service_name,
            "index_name": self.index_name,
            "endpoint": self.endpoint,
        }
