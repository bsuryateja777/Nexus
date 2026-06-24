from typing import Dict, Any, Optional
import logging
from anthropic import Anthropic
from models import Agent, AgentResponse
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ClaudeAgent(BaseAgent):
    """General purpose Claude agent for conversation"""

    def __init__(self, agent_config: Agent, client: Anthropic):
        super().__init__(agent_config)
        self.client = client

    async def process(
        self,
        content: str,
        session_context: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Process message using Claude API

        Args:
            content: User message
            session_context: Session context (unused for Claude)
            parameters: Optional parameters

        Returns:
            AgentResponse with Claude's response
        """

        if not await self.validate_input(content):
            return self._format_response(
                "Please provide a valid message",
                message_type="error"
            )

        try:
            # Build conversation history from session context
            messages = []

            # Add previous messages from conversation for context
            if "messages" in session_context and session_context["messages"]:
                for msg in session_context["messages"]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })

            # Add current user message
            messages.append({"role": "user", "content": content})

            logger.info(f"Claude agent processing with {len(messages)} messages in context")

            # Call Claude API with full conversation history
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=messages
            )

            # Extract response text
            response_text = response.content[0].text

            # Log if response contains tables
            if '|' in response_text:
                logger.info("TABLE DETECTED in response")
                # Check for table headers
                lines = response_text.split('\n')
                for i, line in enumerate(lines):
                    if '|' in line:
                        logger.info(f"Table line {i}: {line[:100]}")
                        if i + 1 < len(lines):
                            logger.info(f"Next line {i+1}: {lines[i+1][:100]}")

            return self._format_response(
                response_text,
                metadata={
                    "usage": {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens
                    }
                }
            )

        except Exception as e:
            logger.error(f"Claude agent error: {str(e)}")
            return self._format_response(
                f"Error: {str(e)}",
                message_type="error"
            )
