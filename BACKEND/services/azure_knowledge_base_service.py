"""
Azure AI Search Knowledge Bases Service
Queries knowledge bases created in Azure AI Search
"""
import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
import aiohttp
from azure.identity import DefaultAzureCredential
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import KnowledgeBaseMessage, KnowledgeBaseMessageTextContent, KnowledgeBaseRetrievalRequest

logger = logging.getLogger(__name__)


class AzureKnowledgeBaseService:
    """Service for querying Azure AI Search Knowledge Bases"""

    def __init__(self):
        """Initialize Knowledge Base service"""
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.api_version = "2025-11-01-preview"

        # Knowledge Base IDs
        self.kb_azure = os.getenv("AZURE_KB_ID_AZURE", "kb-ai-attack-azure")
        self.kb_aws = os.getenv("AZURE_KB_ID_AWS", "kb-ai-attack-aws")

        self.credential = None
        self._session = None

        if self.endpoint:
            self.credential = DefaultAzureCredential()
        else:
            logger.warning("AZURE_SEARCH_ENDPOINT not configured")

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()


    async def _get_auth_header(self) -> Dict[str, str]:
        """Get authentication header for API calls"""
        if not self.credential:
            raise ValueError("Credential not initialized")

        try:
            token = await self._get_token()
            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            logger.error(f"Failed to get auth token: {str(e)}")
            raise

    async def _get_token(self) -> str:
        """Get bearer token for Azure API"""
        # Run synchronous credential in thread pool
        import asyncio
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(
            None,
            lambda: self.credential.get_token("https://search.azure.com/.default").token
        )
        return token

    async def query_knowledge_base(
        self,
        query: str,
        kb_id: str,
        top_k: int = 5,
        reasoning_effort: str = "medium",
        retrieval_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        """Query knowledge base - use RAG-enabled semantic search"""
        if not self.endpoint:
            logger.error("KB service not configured")
            return {"error": "KB service not configured", "answers": []}

        try:
            # Map KB ID to index name (knowledge sources behind the KB)
            index_mapping = {
                "kb-ai-attack-azure": "ai-attack-azure",
                "kb-ai-attack-aws": "ai-attack-aws",
                "document-links": "document-links"
            }

            index_name = index_mapping.get(kb_id, kb_id.replace("kb-", ""))
            url = f"{self.endpoint}/indexes/{index_name}/docs/search?api-version=2024-05-01-preview"

            headers = await self._get_auth_header()
            headers["Content-Type"] = "application/json"

            # Different search fields for different indexes
            if index_name == "document-links":
                search_fields = "chunk,title,url"
            else:
                search_fields = "content_text,document_title"

            payload = {
                "search": query,
                "top": top_k,
                "queryType": "simple",
                "searchFields": search_fields
            }

            session = await self.get_session()

            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    answers = []
                    docs = result.get('value', [])

                    for doc in docs:
                        answer_text = ""
                        source_text = ""

                        # Handle document-links index
                        if index_name == "document-links":
                            # For links, extract title, url, doc_type
                            title = doc.get('title', '').strip()
                            url = doc.get('url', '').strip()
                            chunk = doc.get('chunk', '').strip()
                            doc_type = doc.get('doc_type', 'wiki').strip().lower()

                            # Prefer title, fall back to chunk
                            link_label = title if title else chunk

                            if link_label:
                                # Just plain link text, no badges - frontend handles styling
                                if url:
                                    answer_text = f"[{link_label}]({url})"
                                else:
                                    answer_text = link_label
                                source_text = link_label
                        else:
                            # Handle content indexes (ai-attack-azure, ai-attack-aws)
                            if 'content_text' in doc and isinstance(doc['content_text'], str):
                                answer_text = doc['content_text']
                                source_text = doc.get('document_title', doc.get('content_id', 'Index'))

                        if answer_text:
                            answer_obj = {
                                'answer': answer_text,
                                'source': source_text,
                                'score': doc.get('@search.score', 0)
                            }
                            if index_name == "document-links":
                                answer_obj['doc_type'] = doc_type
                            answers.append(answer_obj)

                    logger.info(f"Index '{index_name}' returned {len(answers)} results")
                    return {"answers": answers}
                else:
                    error_text = await response.text()
                    logger.error(f"Search error {response.status}: {error_text[:150]}")
                    return {"error": f"Search failed: {response.status}", "answers": []}

        except Exception as e:
            logger.error(f"Query error: {str(e)}")
            return {"error": str(e), "answers": []}

    async def search_across_platforms(
        self,
        query: str,
        platform: str = "all",
        top_k: int = 5,
        reasoning_effort: str = "medium"
    ) -> Dict[str, Any]:
        """
        Search across Azure and/or AWS knowledge bases

        Args:
            query: User query
            platform: "azure", "aws", or "all" for both
            top_k: Number of results per KB
            reasoning_effort: Reasoning level

        Returns:
            Combined results from relevant KBs
        """
        results = {
            "query": query,
            "answers_by_platform": {},
            "combined_answers": []
        }

        # Determine which KBs to search based on platform parameter
        kbs_to_search = {}
        if platform == "azure":
            kbs_to_search["Azure"] = self.kb_azure
        elif platform == "aws":
            kbs_to_search["AWS"] = self.kb_aws
        else:  # "all"
            kbs_to_search["Azure"] = self.kb_azure
            kbs_to_search["AWS"] = self.kb_aws

        # Query each KB
        for plat_name, kb_id in kbs_to_search.items():
            try:
                kb_results = await self.query_knowledge_base(
                    query=query,
                    kb_id=kb_id,
                    top_k=top_k,
                    reasoning_effort=reasoning_effort
                )

                results["answers_by_platform"][plat_name] = kb_results.get("answers", [])

                # Add to combined answers with platform tag
                for answer in kb_results.get("answers", []):
                    answer["platform"] = plat_name
                    results["combined_answers"].append(answer)

            except Exception as e:
                logger.error(f"Error querying {plat_name} KB: {str(e)}")
                results["answers_by_platform"][plat_name] = []

        return results

    def format_answer(self, kb_result: Dict[str, Any]) -> str:
        """Format knowledge base response for display"""
        answers = kb_result.get("answers", [])

        if not answers:
            return "No answers found in knowledge base"

        # Take best answer
        best_answer = answers[0]
        answer_text = best_answer.get("answer", "")
        score = best_answer.get("score", 0)
        source = best_answer.get("source", "Unknown")

        formatted = f"{answer_text}\n\n**Source:** {source} (Confidence: {score:.2%})"

        return formatted

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
