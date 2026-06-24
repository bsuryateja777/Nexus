"""
Knowledge Base Agent using Azure AI Search Knowledge Bases
Uses knowledge bases instead of direct semantic search
"""
from typing import Dict, Any, Optional
import logging
import json
import os
from anthropic import Anthropic
from models import Agent, AgentResponse
from agents.base_agent import BaseAgent
from services.azure_knowledge_base_service import AzureKnowledgeBaseService

logger = logging.getLogger(__name__)


class KnowledgeBaseAgent(BaseAgent):
    """Knowledge Base powered agent using Azure AI Search Knowledge Bases"""

    def __init__(self, agent_config: Agent, client: Anthropic):
        super().__init__(agent_config)
        self.client = client
        self.kb_service = AzureKnowledgeBaseService()
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

    def _detect_service(self, query: str) -> tuple[Optional[str], str]:
        """Detect which service the query is about"""
        query_lower = query.lower()
        sorted_aliases = sorted(
            self.service_aliases_map.items(),
            key=lambda x: len(x[0]),
            reverse=True
        )

        for alias, service_id in sorted_aliases:
            if alias in query_lower:
                import re
                pattern = rf'\b{re.escape(alias)}\b'
                if re.search(pattern, query_lower):
                    cleaned_query = re.sub(
                        pattern,
                        '',
                        query_lower,
                        flags=re.IGNORECASE
                    ).strip()
                    return service_id, cleaned_query or query

        return None, query

    async def process(
        self,
        content: str,
        session_context: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Process query using Knowledge Bases"""
        if not await self.validate_input(content):
            return self._format_response(
                "Please provide a valid query",
                message_type="error"
            )

        try:
            if content.strip().lower() in ["/knowledge", "/knowledge list"]:
                return self._list_services()

            query = content.replace("/knowledge", "").strip()

            if not query:
                return self._format_response(
                    "Please provide a search query",
                    message_type="error"
                )

            is_team_member = session_context.get("is_team_member", False) if session_context else False
            detected_service, cleaned_query = self._detect_service(query)

            platform = "all"
            if "azure" in query.lower():
                platform = "azure"
            elif "aws" in query.lower():
                platform = "aws"

            reasoning_effort = parameters.get("reasoning_effort", "medium") if parameters else "medium"

            logger.info(f"Query: '{cleaned_query}', Platform: {platform}, Service: {detected_service}")

            # Get main content from knowledge bases
            kb_results = await self.kb_service.search_across_platforms(
                query=cleaned_query,
                platform=platform,
                top_k=10,
                reasoning_effort=reasoning_effort
            )

            combined_answers = kb_results.get("combined_answers", [])

            if not combined_answers:
                return self._format_response(
                    f"No answers found for: '{cleaned_query}'.\n\n**Tip:** Try rephrasing your query or search for a specific topic.",
                    message_type="error",
                    metadata={
                        "detected_service": detected_service,
                        "query": cleaned_query
                    }
                )

            # Synthesize the main answer from knowledge bases
            response_text = await self._synthesize_kb_answers(cleaned_query, combined_answers)

            # Get related links from document-links index separately
            try:
                # Extract intent and key entities from query
                query_lower = cleaned_query.lower()
                intent_keywords = []
                is_integration_query = False
                required_terms = []

                # Map query patterns to intent keywords and required terms
                if 'connect' in query_lower or 'integration' in query_lower or 'integrate' in query_lower:
                    is_integration_query = True
                    intent_keywords.extend(['integration', 'connect', 'setup'])
                    # For integration queries, extract the services being connected
                    words = query_lower.split()
                    required_terms = [w for w in words if len(w) > 4 and w not in ['how', 'what', 'azure', 'does', 'should', 'account']]

                elif 'register' in query_lower:
                    intent_keywords.extend(['register', 'signup', 'application', 'futurenow'])
                elif 'setup' in query_lower or 'configure' in query_lower:
                    intent_keywords.extend(['setup', 'configure', 'install', 'deploy', 'initialize'])
                elif 'pricing' in query_lower or 'cost' in query_lower:
                    intent_keywords.extend(['pricing', 'cost', 'plans', 'packages'])
                elif 'access' in query_lower or 'request' in query_lower:
                    intent_keywords.extend(['access', 'request', 'apply', 'approval'])
                else:
                    intent_keywords.extend(['guide', 'tutorial', 'how to'])

                # Build enriched query with intent keywords
                enriched_query = cleaned_query
                if intent_keywords:
                    enriched_query = f"{cleaned_query} {' '.join(intent_keywords[:2])}"

                # Add platform filter
                if platform == "azure":
                    enriched_query = f"{enriched_query} azure"
                elif platform == "aws":
                    enriched_query = f"{enriched_query} aws"

                doc_links = await self.kb_service.query_knowledge_base(
                    query=enriched_query,
                    kb_id="document-links",
                    top_k=10
                )
                wiki_links = doc_links.get("answers", [])

                # For integration queries, add metadata to filter later
                for link in wiki_links:
                    link['_required_terms'] = required_terms
                    link['_is_integration'] = is_integration_query

                # Append related links to response if found
                if wiki_links:
                    response_text = await self._append_related_links(response_text, wiki_links, cleaned_query)
            except Exception as e:
                logger.error(f"Failed to fetch related links: {str(e)}", exc_info=True)
                # Continue without related links if query fails

            return self._format_response(
                response_text,
                metadata={
                    "answers_count": len(combined_answers),
                    "wiki_links": len(wiki_links),
                    "query": cleaned_query,
                    "detected_service": detected_service,
                    "is_team_member": is_team_member,
                    "reasoning_effort": reasoning_effort,
                    "knowledge_base_source": "Azure AI Search Knowledge Bases"
                }
            )

        except Exception as e:
            logger.error(f"Knowledge Base Agent error: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return self._format_response(
                f"Error querying knowledge base: {str(e)}",
                message_type="error"
            )

    async def _synthesize_kb_answers(self, query: str, answers: list) -> str:
        """Synthesize KB answers into comprehensive response"""
        if not answers:
            return "No answers found"

        try:
            # Use multiple answers for comprehensive synthesis (up to 5)
            answers_text = "\n---\n".join([
                f"Source: {answer.get('source', 'Unknown')}\nConfidence: {answer.get('score', 0):.0%}\n\n{answer.get('answer', '')}"
                for answer in answers[:5]
            ])

            synthesis_prompt = f"""You are a helpful AI assistant. A user asked: "{query}"

Here are relevant answers from the knowledge base:

{answers_text}

Please provide a comprehensive answer to the user's question based on these sources.
- Synthesize all the information provided
- Keep the response well-organized and detailed
- Use bullet points and sections for clarity
- Include all relevant details, pricing, features, and options
- Mention the source documents if relevant"""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": synthesis_prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Synthesis error: {str(e)}")
            return self._format_kb_answers_simple(answers, query)

    async def _append_related_links(self, response_text: str, wiki_links: list, query: str = '') -> str:
        """Append related links from document-links index to response using semantic relevance"""
        if not wiki_links:
            return response_text

        # Links to explicitly exclude
        exclude_patterns = [
            'blob storage', 'storage connector', 'azure storage',
            'user roles', 'access management', 'entra',
            'compliance', 'terms of use', 'cybersecurity',
            'infrastructure', 'architecture', 'network',
            'pricing model', 'cost', 'billing',
        ]

        def calculate_relevance_score(link_obj: dict, search_score: float, query: str) -> tuple:
            """Calculate relevance considering semantic score, content matching, and query type"""
            link_text = link_obj.get('answer', '').lower()
            is_integration = link_obj.get('_is_integration', False)
            required_terms = link_obj.get('_required_terms', [])

            # Check if link is explicitly excluded
            for pattern in exclude_patterns:
                if pattern.lower() in link_text:
                    return (0, 'excluded')

            # Calculate base relevance score
            relevance = search_score  # Start with semantic score

            # Boost score if query terms appear in link title
            query_terms = [w for w in query.lower().split() if len(w) > 3 and w not in ['azure', 'aws', 'account', 'how', 'does']]
            matches = sum(1 for term in query_terms if term in link_text)
            if matches > 0:
                relevance += (matches * 0.15)  # Strong boost for term matches

            # For integration queries: REQUIRE that related services are mentioned
            if is_integration and required_terms:
                required_matches = sum(1 for term in required_terms if term in link_text)
                if required_matches == 0:
                    # No relevant service mentioned - heavily penalize
                    relevance *= 0.3
                elif required_matches == len(required_terms):
                    # All required services mentioned - strong boost
                    relevance += 0.3
                else:
                    # Some services mentioned - moderate boost
                    relevance += 0.15

            # Check if link is topically related
            topic_keywords = ['futurenow', 'ai attack', 'register', 'setup', 'deploy', 'getting started', 'guide', 'process', 'quickstart', 'tutorial']
            if any(keyword in link_text for keyword in topic_keywords):
                relevance += 0.1  # Boost for topic relevance

            # Penalize generic links without strong matching
            generic_patterns = ['faq', 'overview', 'introduction']
            if any(p in link_text for p in generic_patterns) and matches == 0:
                relevance *= 0.7  # Reduce score for generic links without term matches

            return (relevance, 'included')

        links_section = "\n\n**Related Pages:**\n"
        link_count = 0

        # Score and sort all links
        scored_links = []
        for link in wiki_links:
            link_text = link.get('answer', '').strip()
            search_score = link.get('score', 0)

            if link_text:
                relevance, status = calculate_relevance_score(link, search_score, query)
                # Stricter threshold for integration queries, more lenient for general queries
                min_threshold = 0.65 if link.get('_is_integration') else 0.5
                if status == 'included' and relevance > min_threshold:
                    scored_links.append((relevance, link_text))

        # Sort by relevance score (highest first)
        scored_links.sort(reverse=True)

        for relevance, link_text in scored_links[:5]:  # Show top 5 most relevant
            links_section += f"- {link_text}\n"
            link_count += 1

        if link_count > 0:  # Only add if we have relevant links
            return response_text + links_section
        return response_text

    def _format_kb_answers_simple(self, answers: list, query: str) -> str:
        """Fallback: Format knowledge base answers for display"""
        if not answers:
            return "No answers found"

        formatted_answers = []

        # Group by platform if multiple answers
        answers_by_platform = {}
        for answer in answers:
            platform = answer.get("platform", "Unknown")
            if platform not in answers_by_platform:
                answers_by_platform[platform] = []
            answers_by_platform[platform].append(answer)

        # Format each platform's answers
        for platform, platform_answers in answers_by_platform.items():
            formatted_answers.append(f"## {platform} Results\n")

            for i, answer in enumerate(platform_answers[:2], 1):  # Show top 2 per platform
                answer_text = answer.get("answer", "")[:500]  # Truncate to 500 chars
                score = answer.get("score", 0)
                source = answer.get("source", "Unknown source")

                formatted = f"""
**Answer {i}:** {answer_text}...

*Source:* {source} (Confidence: {score:.0%})
"""
                formatted_answers.append(formatted)

        return "\n".join(formatted_answers)

    def _list_services(self) -> AgentResponse:
        """List available services"""
        if not self.services:
            return self._format_response(
                "No services available",
                message_type="error"
            )

        services_list = "# Available Services\n\n"
        for service_id, service in self.services.items():
            name = service.get("name")
            aliases = ", ".join(service.get("aliases", []))
            description = service.get("description", "")
            services_list += f"- **{name}** (`{aliases}`)\n  {description}\n\n"

        return self._format_response(services_list)

    async def close(self):
        """Clean up resources"""
        await self.kb_service.close()
