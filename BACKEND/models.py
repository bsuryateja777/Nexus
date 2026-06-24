from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class Agent(BaseModel):
    """Agent configuration and metadata"""
    id: str
    name: str
    description: str
    model: str
    system_prompt: str
    max_tokens: int = 1024
    temperature: float = 0.7
    tools: List[str] = []
    is_active: bool = True


class SkillMetadata(BaseModel):
    """Skill/agent information for frontend"""
    skill_id: str
    agent_id: str
    name: str
    description: str
    parameters: Dict[str, Any] = {}
    aliases: List[str] = []


class Message(BaseModel):
    """Extended message model with agent tracking"""
    id: str
    agent_id: Optional[str] = None
    role: str
    content: str
    message_type: str = "text"
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class SkillRequest(BaseModel):
    """Request model for /chat/message endpoint"""
    content: str
    skill_id: Optional[str] = None
    parameters: Dict[str, Any] = {}


class AgentResponse(BaseModel):
    """Response model from agents"""
    content: str
    agent_id: str
    agent_name: str
    message_type: str = "text"
    metadata: Dict[str, Any] = {}


class ChatMessage(BaseModel):
    """Backward compatibility with existing model"""
    content: str


class ChatResponse(BaseModel):
    """Chat message response"""
    content: str
    role: str = "assistant"
    generated_title: str | None = None  # For new conversations, AI-generated title
