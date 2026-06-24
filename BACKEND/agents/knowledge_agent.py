from typing import Dict, Any, Optional, List, Tuple
import logging
import re
import json
import os
from anthropic import Anthropic
from azure.search.documents import SearchClient
from models import Agent, AgentResponse
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class KnowledgeAgent(BaseAgent):
    """Azure-powered knowledge base search and synthesis agent"""

    def __init__(self, agent_config: Agent, client: Anthropic):
        super().__init__(agent_config)
        self.client = client
        # Azure services will be injected
        self.cognitive_search = None
        self.storage_service = None
        self.doc_intelligence = None
        self.services = self._load_services()
        self.service_aliases_map = self._build_alias_map()

    def _load_services(self) -> Dict[str, Dict[str, Any]]:
        """Load services from services_config.json"""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "services_config.json"
            )
            with open(config_path, 'r') as f:
                config = json.load(f)
                return {
                    service["id"]: service
                    for service in config.get("services", [])
                }
        except Exception as e:
            logger.warning(f"Failed to load services config: {str(e)}")
            return {}

    def _build_alias_map(self) -> Dict[str, str]:
        """Create mapping from aliases to service IDs"""
        alias_map = {}
        for service_id, service in self.services.items():
            for alias in service.get("aliases", []):
                alias_map[alias.lower()] = service_id
        return alias_map

    def set_azure_services(self, cognitive_search, storage_service, doc_intelligence):
        """Inject Azure services"""
        self.cognitive_search = cognitive_search
        self.storage_service = storage_service
        self.doc_intelligence = doc_intelligence
        logger.info("✓ Azure services injected into Knowledge Agent")

    def set_search_engine(self, hybrid_search):
        """Legacy method - kept for compatibility"""
        pass

    async def _fetch_servicelinks(self, query: str) -> List[Dict[str, Any]]:
        """
        Fetch relevant documentation links from ServiceLinks index

        Args:
            query: User query to search for related documentation

        Returns:
            List of servicelinks dicts with title, url, description, category
        """
        servicelinks = []

        if not self.cognitive_search or not self.cognitive_search.is_configured():
            logger.debug("ServiceLinks: Cognitive Search not configured")
            return servicelinks

        try:
            servicelinks_index = os.getenv("AZURE_SEARCH_SERVICELINKS_INDEX", "")
            if not servicelinks_index:
                logger.debug("ServiceLinks index not configured in .env")
                return servicelinks

            logger.info(fSearching ServiceLinks index: {servicelinks_index} for query: '{query}'")

            # Search servicelinks index directly using SearchClient (not the transformed search method)
            # because the servicelinks index has a different schema (with url, description fields)
            if not self.cognitive_search.endpoint or not self.cognitive_search.credential:
                logger.error("ServiceLinks: Missing endpoint or credential for search")
                return servicelinks

            try:
                search_client = SearchClient(
                    endpoint=self.cognitive_search.endpoint,
                    index_name=servicelinks_index,
                    credential=self.cognitive_search.credential
                )
                logger.info(f"Created SearchClient for {servicelinks_index}")
            except Exception as e:
                logger.error(f"Failed to create SearchClient for {servicelinks_index}: {str(e)}")
                return servicelinks

            try:
                results = search_client.search(search_text=query, top=10)
                result_list = list(results)
                logger.debug(f"ServiceLinks search returned {len(result_list)} raw results")
            except Exception as e:
                logger.error(f"ServiceLinks search error: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                return servicelinks

            # Filter and format servicelinks - only include highly relevant ones
            # Higher score = more relevant. Keep only top 3-5 most relevant
            scored_links = []

            for result in result_list:
                try:
                    # Extract fields from docs-links index
                    title = result.get("title") or ""
                    url = result.get("url") or ""
                    description = result.get("description") or ""
                    doc_type = result.get("doc_type") or "Wikipedia"
                    platform = result.get("platform") or "Azure"  # Default to Azure for backwards compatibility
                    score = result.get("@search.score", 0)  # Relevance score

                    link_data = {
                        "title": title,
                        "url": url,
                        "description": description,
                        "category": doc_type,
                        "platform": platform,
                        "score": score
                    }

                    # Only include if we have title and URL, and score > 0.3 (moderate relevance)
                    if link_data["title"] and link_data["url"] and score > 0.3:
                        scored_links.append((link_data, score))
                        logger.debug(f"  ✓ Candidate: [{platform}] {link_data['title']} (score: {score:.2f})")
                    else:
                        logger.debug(f"  ✗ Skipped (score {score:.2f} or missing fields): {title}")

                except Exception as e:
                    logger.debug(f"Error formatting servicelink: {str(e)}")
                    continue

            # Sort by score and keep only top 5 most relevant
            scored_links.sort(key=lambda x: x[1], reverse=True)
            servicelinks = [link for link, score in scored_links[:5]]

            logger.info(f"ServiceLinks: Found {len(servicelinks)} highly relevant links")

        except Exception as e:
            logger.error(f"❌ ServiceLinks search failed: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't fail the entire request if servicelinks search fails
            servicelinks = []

        return servicelinks

    async def process(
        self,
        content: str,
        session_context: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process knowledge base query with intelligent service routing

        Args:
            content: User query
            session_context: Session context
            parameters: Query parameters

        Returns:
            AgentResponse with search results or synthesized response
        """

        if not await self.validate_input(content):
            return self._format_response(
                "Please provide a valid query",
                message_type="error"
            )

        try:
            # Handle special commands
            if content.strip().lower() in ["/knowledge", "/knowledge list"]:
                return self._list_services()

            # Remove /knowledge prefix if present
            query = content.replace("/knowledge", "").strip()

            if not query:
                return self._format_response(
                    "Please provide a search query after /knowledge command",
                    message_type="error"
                )

            # Extract user role from session context
            is_team_member = session_context.get("is_team_member", False) if session_context else False

            # Detect which service the query is about
            detected_service, cleaned_query = self._detect_service(query)

            # Get service metadata
            metadata_service = None
            if detected_service:
                service_info = self.services.get(detected_service)
                metadata_service = service_info.get("name") if service_info else None

            # Expand query with synonyms for better matching
            # (Removed simplification - it was causing inconsistent results)
            expanded_query = self._expand_query(cleaned_query)
            logger.debug(f"Query expansion: '{cleaned_query}' → '{expanded_query}'")

            # Search using Azure Cognitive Search with semantic ranking
            search_results = []
            wikipedia_results = []
            confluence_results = []
            passage_search_results = []  # Keep track of passage results for fallback decision

            # Don't filter by service_id for RAG indexes (they don't have service_id metadata)
            index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "")
            should_filter_by_service = "rag" not in index_name.lower()

            if self.cognitive_search and self.cognitive_search.is_configured():
                # Use semantic search for better RAG results
                # Semantic ranking reorders results based on semantic relevance
                top_k = parameters.get("top_k", 15) if parameters else 15

                raw_results = await self.cognitive_search.search(
                    query=expanded_query,
                    service_id=detected_service if should_filter_by_service else None,
                    top_k=top_k,
                    use_semantic_search=True
                )

                # Threshold for finding relevant docs, then limit quantity
                # Semantic scores: 0.0-4.0 (higher is better). 0.5 finds good matches
                # Keyword scores: 0.0-5.0. 0.5 for relevance
                # We'll get more results but only return top 2 (quality by limiting quantity)
                relevance_threshold_semantic = 0.5  # Find relevant docs
                relevance_threshold_keyword = 0.5   # Consistent threshold

                for result in raw_results:
                    # Prefer semantic score for better relevance (RAG optimized)
                    semantic_score = result.get("semantic_score")
                    keyword_score = result.get("score", 0)

                    # Use semantic score if available, otherwise use keyword score
                    if semantic_score is not None:
                        score = semantic_score
                        threshold = relevance_threshold_semantic
                    else:
                        score = keyword_score
                        threshold = relevance_threshold_keyword

                    if score >= threshold:
                        document_path = result.get("document_path", "").lower()

                        # Categorize by source (if document_path exists)
                        if document_path:
                            if "wikipedia" in document_path:
                                wikipedia_results.append(result)
                            elif "confluence" in document_path:
                                confluence_results.append(result)
                            else:
                                # If source not specified, treat as available to all
                                wikipedia_results.append(result)
                        else:
                            # No document_path - treat as available to all (RAG index style)
                            wikipedia_results.append(result)

                # Apply role-based filtering - TOP 2 RELEVANT RESULTS
                if not is_team_member:
                    # Non-team users only see top 2 Wikipedia results
                    search_results = wikipedia_results[:2]
                else:
                    # Team members see top 2 combined results, with Wikipedia first
                    search_results = (wikipedia_results + confluence_results)[:2]

                # Save passage results for hybrid RAG fallback decision
                passage_search_results = search_results.copy()

                logger.debug(f"Semantic search found {len(search_results)} relevant results (semantic ranking applied)")
            else:
                logger.warning("Azure Cognitive Search not configured")

            # Fetch relevant documentation links from ServiceLinks search index
            servicelinks = await self._fetch_servicelinks(cleaned_query)

            # HYBRID RAG: Check if passage search quality is low, fallback to full documents
            fallback_to_full_docs = False
            if passage_search_results and self._should_fallback_to_full_docs(passage_search_results):
                logger.info("🔄 Triggering hybrid RAG: Fallback to full documents")
                fallback_to_full_docs = True

                # Extract document names from passage results for full retrieval
                doc_names = [
                    result.get("document_name")
                    for result in passage_search_results
                    if result.get("document_name")
                ]

                if doc_names:
                    # Retrieve full documents from storage
                    full_docs = await self._retrieve_full_documents(doc_names)
                    if full_docs:
                        # Replace passage results with full documents for synthesis
                        logger.info(f"📄 Using {len(full_docs)} full document(s) instead of passages for synthesis")
                        search_results = full_docs
                    else:
                        logger.info("⚠️  Full document retrieval failed, using passage results")
                else:
                    logger.debug("No document names found for full retrieval")

            # Smart servicelinks filtering based on doc relevancy
            # If high relevancy docs found: show only top 2 links (avoid clutter)
            # If no/low relevancy docs: show all links (help guide user)
            if search_results:
                # Check if docs have high relevancy (score >= 2.0)
                has_high_relevancy = any(
                    result.get("semantic_score", result.get("score", 0)) >= 2.0
                    for result in search_results
                )

                if has_high_relevancy:
                    # High quality docs found - show only top 1 servicelink
                    servicelinks = servicelinks[:1]
                    logger.debug(f"High relevancy docs found - showing top 1 servicelink")
                # else: low relevancy docs - show all servicelinks
            # else: no docs found - show all servicelinks (already fetched)

            # Always synthesize with Claude for intelligent analysis and rephrasing
            needs_synthesis = True  # Always let Claude analyze and answer intelligently

            if not search_results:
                # If no passages found but we have servicelinks, try secondary search using servicelink titles
                if servicelinks and self.cognitive_search and self.cognitive_search.is_configured():
                    logger.info(f"🔄 No passages found, but {len(servicelinks)} servicelinks available - attempting secondary search")

                    fallback_to_full_docs = True
                    doc_names_to_fetch = set()

                    # Try searching for documents using servicelink titles as queries
                    for link in servicelinks[:3]:  # Try top 3 servicelinks
                        link_title = link.get("title", "")
                        if link_title:
                            logger.debug(f"Secondary search using servicelink title: '{link_title}'")
                            try:
                                secondary_results = await self.cognitive_search.search(
                                    query=link_title,
                                    service_id=detected_service if should_filter_by_service else None,
                                    top_k=5,
                                    use_semantic_search=True
                                )

                                # Collect document names from secondary search
                                for result in secondary_results:
                                    doc_name = result.get("document_name")
                                    if doc_name and result.get("semantic_score", result.get("score", 0)) > 0.3:
                                        doc_names_to_fetch.add(doc_name)
                            except Exception as e:
                                logger.debug(f"Secondary search failed for '{link_title}': {str(e)}")
                                continue

                    # Retrieve full documents using collected names
                    if doc_names_to_fetch:
                        full_docs = await self._retrieve_full_documents(list(doc_names_to_fetch))
                        if full_docs:
                            logger.info(f"📄 Retrieved {len(full_docs)} full document(s) via secondary search for synthesis")
                            search_results = full_docs
                            needs_synthesis = True
                        else:
                            logger.info("⚠️  Secondary search found documents but full retrieval failed")
                    else:
                        logger.debug("No document names found in secondary search results, attempting fallback search with lower threshold")

                # If still no results, do one more aggressive search with MUCH LOWER threshold on expanded query
                if not search_results and self.cognitive_search and self.cognitive_search.is_configured():
                    logger.info(f"🔄 Secondary search failed, attempting aggressive fallback with lower threshold")

                    try:
                        fallback_results = await self.cognitive_search.search(
                            query=expanded_query,  # Use expanded query with synonyms
                            service_id=detected_service if should_filter_by_service else None,
                            top_k=10,
                            use_semantic_search=True
                        )

                        # Use VERY LOW threshold for fallback (just to get something)
                        low_threshold = 0.1

                        for result in fallback_results:
                            score = result.get("semantic_score", result.get("score", 0))
                            if score >= low_threshold:
                                doc_name = result.get("document_name")
                                if doc_name:
                                    logger.debug(f"Fallback: Found document '{doc_name}' with score {score:.2f}")

                                    # Retrieve full document
                                    full_docs = await self._retrieve_full_documents([doc_name])
                                    if full_docs:
                                        search_results = full_docs
                                        logger.info(f"✅ Retrieved document via aggressive fallback: {doc_name}")
                                        fallback_to_full_docs = True
                                        break

                    except Exception as e:
                        logger.debug(f"Aggressive fallback search failed: {str(e)}")

                # Still no results after attempting servicelinks fallback
                if not search_results:
                    suggestion = ""
                    if detected_service:
                        suggestion = f"\n\n**Suggestion:** Try a more general search related to {metadata_service}. Or check if the knowledge base is fully populated."
                    else:
                        suggestion = "\n\n**Suggestion:** Try rephrasing your query with different keywords. Example: 'data warehouse setup' or 'cloud architecture basics'"

                    return self._format_response(
                        f"No articles found for: '{cleaned_query}'{suggestion}",
                        message_type="error",
                        metadata={
                            "detected_service": detected_service,
                            "servicelinks": servicelinks  # Include servicelinks even when no docs found
                        }
                    )

            # If synthesis needed, use Claude to summarize/explain
            if needs_synthesis:
                response = await self._synthesize_with_claude(cleaned_query, search_results, is_team_member)
            else:
                # Return raw results formatted
                response = self._format_search_results(search_results, is_team_member=is_team_member)

            # Organize results by source for metadata
            wiki_results = [r for r in search_results if "wikipedia" in r.get("document_path", "").lower()]
            conf_results = [r for r in search_results if "confluence" in r.get("document_path", "").lower()]

            return self._format_response(
                response,
                metadata={
                    "search_results_count": len(search_results),
                    "query": cleaned_query,
                    "detected_service": detected_service,
                    "service_name": metadata_service,
                    "synthesized": needs_synthesis,
                    "is_team_member": is_team_member,
                    "hybrid_rag_fallback": fallback_to_full_docs,
                    "results_by_source": {
                        "wikipedia": [
                            {
                                "title": r.get("title", "Unknown"),
                                "score": r.get("score", 0)
                            }
                            for r in wiki_results
                        ],
                        "confluence": [
                            {
                                "title": r.get("title", "Unknown"),
                                "score": r.get("score", 0)
                            }
                            for r in conf_results
                        ] if is_team_member else []
                    },
                    "results": [
                        {
                            "title": r.get("title", "Unknown"),
                            "source": "Confluence" if "confluence" in r.get("document_path", "").lower() else "Wikipedia",
                            "score": r.get("score", 0)
                        }
                        for r in search_results
                    ],
                    "servicelinks": servicelinks
                }
            )

        except Exception as e:
            logger.error(f"Knowledge agent error: {str(e)}")
            return self._format_response(
                f"Error searching knowledge base: {str(e)}",
                message_type="error"
            )

    def _should_synthesize(self, query: str) -> bool:
        """
        Smart detection: determine if query needs synthesis

        Specific queries (looking for data) → raw results
        General queries (looking for explanation) → synthesis
        """
        # Specific query patterns (want raw data/values)
        specific_patterns = [
            r"what.*value.*\?",
            r"where.*is.*\?",
            r"find.*",
            r"get.*",
            r"show.*",
            r"list.*",
            r"which.*",
        ]

        # General query patterns (want explanation)
        general_patterns = [
            r"explain.*",
            r"how.*",
            r"why.*",
            r"describe.*",
            r"what.*is.*",
            r"tell.*about.*",
            r"summarize.*",
        ]

        query_lower = query.lower()

        # Check specific patterns first
        for pattern in specific_patterns:
            if re.search(pattern, query_lower):
                return False

        # Check general patterns
        for pattern in general_patterns:
            if re.search(pattern, query_lower):
                return True

        # Default: if query has question mark and more than 4 words, likely needs synthesis
        if "?" in query and len(query.split()) > 4:
            return True

        return False

    async def _synthesize_with_claude(
        self,
        query: str,
        search_results: list,
        is_team_member: bool = False
    ) -> str:
        """Use Claude to synthesize/explain search results"""

        context = self._format_search_results(search_results, is_team_member=is_team_member)

        synthesis_prompt = f"""You are an intelligent assistant analyzing knowledge base documents.

User Query: {query}

Knowledge Base Articles (with extracted content and visual elements):
{context}

Please:
1. Analyze the provided document content carefully
2. Extract and rephrase the relevant information in clear, simple language
3. Provide a comprehensive answer that directly addresses the user's question
4. Explain concepts clearly for someone unfamiliar with the topic
5. Use markdown formatting (headers, bullet points, bold for emphasis) for readability
6. When document contains images/figures, reference them naturally in your explanation
   Example: "As shown in Figure 1, the architecture includes..." or "The diagram illustrates..."
7. Provide practical examples or use cases where relevant
8. Do not mention or attempt to generate images - only reference images that are mentioned in the source material"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": synthesis_prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude synthesis error: {str(e)}")
            # Fall back to formatted results if synthesis fails
            return context

    async def _retrieve_full_documents(self, document_names: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve full document content by reconstructing from all passages

        This method searches for all passages belonging to the given document names
        and reconstructs the full documents by concatenating them in order.

        Args:
            document_names: List of document file names to retrieve

        Returns:
            List of documents with reconstructed full content
        """
        full_docs = []

        if not self.cognitive_search or not self.cognitive_search.is_configured():
            logger.warning("Cognitive Search not available for document reconstruction")
            return full_docs

        try:
            for doc_name in document_names:
                logger.debug(f"Reconstructing full document from passages: {doc_name}")

                try:
                    # Search for all passages that belong to this document
                    # Search by document name to find all related passages
                    doc_passages = await self.cognitive_search.search(
                        query=doc_name,
                        top_k=100,
                        use_semantic_search=False
                    )

                    # Filter to only exact matches from this document, sorted by chunk order
                    matching_passages = []
                    for passage in doc_passages:
                        if passage.get("document_name") == doc_name:
                            # Try to get chunk number for ordering
                            chunk_num = passage.get("chunk_num", 0)
                            matching_passages.append((chunk_num, passage))

                    if matching_passages:
                        # Sort by chunk number to maintain order
                        matching_passages.sort(key=lambda x: x[0])

                        # Concatenate all passage content
                        full_content = "\n\n---\n\n".join(
                            passage.get("content", passage.get("chunk", ""))
                            for _, passage in matching_passages
                        )

                        full_docs.append({
                            "document_name": doc_name,
                            "content": full_content,
                            "title": matching_passages[0][1].get("title", doc_name) if matching_passages else doc_name,
                            "source": "full_document_reconstructed",
                            "chunk_count": len(matching_passages)
                        })
                        logger.info(f"✓ Reconstructed full document '{doc_name}' from {len(matching_passages)} passages")
                    else:
                        logger.debug(f"No passages found for document: {doc_name}")

                except Exception as e:
                    logger.debug(f"Failed to reconstruct {doc_name}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error reconstructing full documents: {str(e)}")

        return full_docs

    def _should_fallback_to_full_docs(self, search_results: List[Dict[str, Any]]) -> bool:
        """
        Determine if passage-based search quality is too low and fallback to full docs

        Fallback conditions:
        - All results have low semantic scores (< 2.0)
        - Or we have very few relevant results (< 2 docs with decent scores)

        Args:
            search_results: List of passage-based search results

        Returns:
            True if should fallback to full documents, False otherwise
        """
        if not search_results:
            return False

        # Check highest scoring result
        max_score = max(
            result.get("semantic_score", result.get("score", 0))
            for result in search_results
        )

        # If best result has low relevance, fallback to full documents
        if max_score < 2.0:
            logger.info(f"Low passage relevance (max score: {max_score:.2f}) - triggering full document fallback")
            return True

        return False

    def _format_search_results(self, results: list, detected_service: str = None, is_team_member: bool = False) -> str:
        """Format Azure search results for display or synthesis, separated by source"""

        if not results:
            return "No results found."

        # Separate results by source
        wikipedia_results = [r for r in results if "wikipedia" in r.get("document_path", "").lower()]
        confluence_results = [r for r in results if "confluence" in r.get("document_path", "").lower()]

        # Handle items without clear source classification
        unclassified = [r for r in results if r not in wikipedia_results and r not in confluence_results]
        if unclassified:
            wikipedia_results.extend(unclassified)

        formatted = []

        # Format Wikipedia results
        if wikipedia_results:
            formatted.append("## Wikipedia Results\n")
            for i, result in enumerate(wikipedia_results, 1):
                formatted.append(self._format_single_result(result, i))

        # Format Confluence results (only if user is team member)
        if is_team_member and confluence_results:
            formatted.append("\n## Confluence Results\n")
            for i, result in enumerate(confluence_results, 1):
                formatted.append(self._format_single_result(result, i))
        elif confluence_results and not is_team_member:
            formatted.append("\n**Note:** Confluence documents are available to team members only.")

        return "\n".join(formatted)

    def _format_single_result(self, result: dict, index: int) -> str:
        """Format a single search result"""
        title = result.get("title", result.get("document_name", "Untitled"))
        content = result.get("content") or result.get("chunk", "No content")
        document_name = result.get("document_name", "Unknown")
        score = result.get("score", 0)

        section = f"""
### Result {index}: {title}
**Document:** {document_name} (Relevance Score: {score:.2f})

{content}
"""

        # Add image information if available
        images_metadata_str = result.get("images_metadata", "")
        if images_metadata_str:
            try:
                images_data = json.loads(images_metadata_str)
                if images_data:
                    section += "\n**Visual Elements:**\n"
                    for img in images_data:
                        img_desc = img.get("description", f"Image {img.get('index', '?')}")
                        img_page = img.get("page", "unknown")
                        section += f"- {img_desc} (Page {img_page})\n"
            except (json.JSONDecodeError, TypeError):
                pass

        has_visual = result.get("has_visual_content", False)
        if has_visual and not images_metadata_str:
            section += "\n*Note: This document contains visual elements/images.*\n"

        return section

    def _simplify_query(self, query: str) -> str:
        """
        Extract key terms from long/complex queries for better search matching

        Example: "i have an account so based on current configuration..."
                 → "request API keys authentication"
        """
        # Keywords that indicate key search terms
        key_indicators = {
            "how": "how to",
            "what": "what is",
            "why": "why",
            "request": "request",
            "api": "api keys",
            "keys": "api keys",
            "auth": "authentication",
            "configure": "configuration",
            "setup": "setup",
            "integrate": "integration",
            "connect": "connection",
        }

        query_lower = query.lower()
        found_terms = []

        for indicator, full_term in key_indicators.items():
            if indicator in query_lower:
                found_terms.append(full_term)

        # If found key terms, use them; otherwise return original
        if found_terms:
            simplified = " ".join(found_terms)
            logger.debug(f"Query simplified: '{query[:50]}...' → '{simplified}'")
            return simplified

        return query

    def _expand_query(self, query: str) -> str:
        """
        Expand query with synonyms and phrase matching for better search precision

        Args:
            query: Original query

        Returns:
            Expanded query with additional search terms
        """
        expanded_parts = [f'"{query}"']  # Start with exact phrase

        # Add common synonyms for key terms
        synonym_map = {
            "setup": ["installation", "install", "configure", "configuration"],
            "error": ["issue", "problem", "failure", "bug"],
            "data": ["dataset", "information", "records"],
            "performance": ["speed", "optimization", "optimize", "efficient"],
            "connect": ["integration", "integrate", "connection", "link"],
            "query": ["sql", "search", "filter"],
            "create": ["build", "generate", "make"],
            "delete": ["remove", "drop"],
            "update": ["modify", "change", "alter"],
            "request": ["apply", "ask for", "submit"],
            "authentication": ["auth", "login", "credential", "password"],
            "api": ["api key", "endpoint", "service"],
            "exception": ["request", "exemption", "waiver", "approval", "permission"],
            "get": ["obtain", "request", "receive", "acquire"],
            "architecture": ["design", "structure", "infrastructure", "layout"],
        }

        for keyword, synonyms in synonym_map.items():
            if keyword.lower() in query.lower():
                expanded_parts.append(f"({keyword} OR {' OR '.join(synonyms)})")
                break

        return " ".join(expanded_parts)

    def _detect_service(self, query: str) -> Tuple[Optional[str], str]:
        """
        Detect which service the query is about using aliases

        Returns:
            (service_id, cleaned_query) - service_id is None if no service detected
        """
        query_lower = query.lower()

        # Check aliases from longest to shortest (avoid partial matches)
        sorted_aliases = sorted(
            self.service_aliases_map.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for alias, service_id in sorted_aliases:
            pattern = rf'\b{re.escape(alias)}\b'
            # Look for alias as whole word or phrase in query
            if re.search(pattern, query_lower):
                # Remove the alias from query to get cleaned version
                cleaned_query = re.sub(
                    pattern,
                    '',
                    query_lower,
                    flags=re.IGNORECASE
                ).strip()
                return service_id, cleaned_query or query

        return None, query


    async def debug_check_servicelinks(self) -> Dict[str, Any]:
        """Debug helper to check if servicelinks index has data"""
        try:
            servicelinks_index = os.getenv("AZURE_SEARCH_SERVICELINKS_INDEX", "")
            if not servicelinks_index:
                return {"status": "error", "message": "ServiceLinks index not configured"}

            if not self.cognitive_search or not self.cognitive_search.is_configured():
                return {"status": "error", "message": "Cognitive Search not configured"}

            # Try a wildcard search to see if any documents exist
            results = await self.cognitive_search.search(
                query="*",
                top_k=10,
                use_semantic_search=False,
                index_name=servicelinks_index
            )

            return {
                "status": "ok",
                "index": servicelinks_index,
                "total_docs_found": len(results),
                "sample_docs": [
                    {
                        "title": r.get("title") or r.get("title_Data_Column", "N/A"),
                        "url": r.get("url", "N/A"),
                    }
                    for r in results[:5]
                ]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _list_services(self) -> AgentResponse:
        """List all available services in the knowledge base"""
        if not self.services:
            return self._format_response(
                "No services available in configuration",
                message_type="error"
            )

        services_list = "# Available Services for Knowledge Search\n\n"

        # Group by category
        categories = {}
        for service_id, service in self.services.items():
            category = service.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(service)

        for category, services in sorted(categories.items()):
            services_list += f"## {category.title().replace('-', ' ')}\n\n"
            for service in sorted(services, key=lambda x: x.get("name")):
                name = service.get("name")
                aliases = ", ".join(service.get("aliases", []))
                description = service.get("description", "")
                services_list += f"- **{name}** (`{aliases}`)\n  {description}\n\n"

        services_list += "\n**Usage:** Type `/knowledge snowflake <your question>` to search for a specific service.\n"
        services_list += "**Example:** `/knowledge what is snowflake data warehouse`\n"

        return self._format_response(
            services_list,
            metadata={"total_services": len(self.services)}
        )
