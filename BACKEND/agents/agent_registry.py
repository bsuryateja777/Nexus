from typing import Dict, List, Optional
from models import Agent, SkillMetadata
from agents.base_agent import BaseAgent


class AgentRegistry:
    """Registry for managing available agents"""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._skills: Dict[str, SkillMetadata] = {}

    def register_agent(
        self,
        agent: BaseAgent,
        skill_metadata: SkillMetadata
    ) -> None:
        """Register a new agent with its skill metadata"""
        self._agents[agent.id] = agent
        self._skills[agent.id] = skill_metadata

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID"""
        return self._agents.get(agent_id)

    def get_skill(self, skill_id: str) -> Optional[SkillMetadata]:
        """Get skill metadata by ID"""
        return self._skills.get(skill_id)

    def list_agents(self) -> List[BaseAgent]:
        """List all registered agents"""
        return list(self._agents.values())

    def list_skills(self) -> List[SkillMetadata]:
        """List all available skills"""
        return list(self._skills.values())

    def get_active_agents(self) -> List[BaseAgent]:
        """Get only active agents"""
        return [agent for agent in self._agents.values() if agent.config.is_active]

    def find_agent_by_skill_id(self, skill_id: str) -> Optional[BaseAgent]:
        """Find agent by skill ID or alias"""
        # Direct skill ID match
        if skill_id in self._agents:
            return self._agents[skill_id]

        # Check aliases
        for agent_id, skill in self._skills.items():
            if skill_id in skill.aliases or skill_id == skill.skill_id:
                return self._agents.get(agent_id)

        return None
