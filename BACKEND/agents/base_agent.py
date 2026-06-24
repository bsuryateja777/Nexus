from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from models import Agent, AgentResponse


class BaseAgent(ABC):
    """Abstract base class for all agents"""

    def __init__(self, agent_config: Agent):
        self.config = agent_config
        self.id = agent_config.id
        self.name = agent_config.name
        self.model = agent_config.model
        self.system_prompt = agent_config.system_prompt
        self.max_tokens = agent_config.max_tokens
        self.temperature = agent_config.temperature

    @abstractmethod
    async def process(
        self,
        content: str,
        session_context: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process request and return structured response

        Args:
            content: User message/query
            session_context: Current session data (user_id, subscription, etc.)
            parameters: Additional parameters for the skill

        Returns:
            AgentResponse with content and metadata
        """
        pass

    async def validate_input(self, content: str) -> bool:
        """Validate input before processing"""
        return len(content.strip()) > 0

    def _format_response(
        self,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """Helper to format agent response"""
        return AgentResponse(
            content=content,
            agent_id=self.id,
            agent_name=self.name,
            message_type=message_type,
            metadata=metadata or {}
        )
