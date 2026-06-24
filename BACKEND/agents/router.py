from typing import Dict, Any, Optional
import logging
import os
from agents.base_agent import BaseAgent
from agents.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


class AgentRouter:
    """Routes messages to appropriate agents"""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    async def route(
        self,
        content: str,
        session_context: Dict[str, Any],
        explicit_skill_id: Optional[str] = None
    ) -> BaseAgent:
        """
        Determine which agent should handle the message

        Args:
            content: User message
            session_context: Session data
            explicit_skill_id: Optional explicit skill selection

        Returns:
            BaseAgent to handle the request
        """

        # If user explicitly selected a skill, use it
        if explicit_skill_id:
            agent = self.registry.find_agent_by_skill_id(explicit_skill_id)
            if agent:
                return agent

        # Auto-detect based on message content
        if content.strip().startswith("/knowledge"):
            agent = self.registry.find_agent_by_skill_id("knowledge")
            if agent:
                return agent

        if content.strip().startswith("/azure"):
            agent = self.registry.find_agent_by_skill_id("azure")
            if agent:
                return agent

        # Check if KB agent is enabled and query looks like knowledge search
        use_kb_agent = os.getenv("USE_KB_AGENT", "true").lower() == "true"
        print(f"\n=== ROUTER: USE_KB_AGENT = {use_kb_agent}, query = '{content}' ===")

        if use_kb_agent:
            knowledge_keywords = [
                "developer package", "azure", "ai attack", "knowledge",
                "how to", "what is", "configure", "setup", "architecture",
                "acp", "authentication", "exception", "playground", "pricing",
                "account", "access", "install", "integration", "api"
            ]

            content_lower = content.lower()

            if any(keyword in content_lower for keyword in knowledge_keywords):
                print(f"=== ROUTER: Found knowledge keyword, routing to KNOWLEDGE AGENT ===")
                agent = self.registry.find_agent_by_skill_id("knowledge")
                if agent:
                    print(f"=== ROUTER: KNOWLEDGE AGENT found and returning ===")
                    return agent
                else:
                    print(f"=== ROUTER: KNOWLEDGE AGENT not found in registry ===")
            else:
                print(f"=== ROUTER: No knowledge keywords found ===")
        else:
            print(f"=== ROUTER: KB Agent is disabled ===")

        print(f"=== ROUTER: Defaulting to CLAUDE AGENT ===")


        # Default to Claude agent for general chat
        agent = self.registry.find_agent_by_skill_id("claude")
        if agent:
            return agent

        # Fallback: get first available agent
        agents = self.registry.get_active_agents()
        if agents:
            return agents[0]

        raise ValueError("No agents available for routing")
