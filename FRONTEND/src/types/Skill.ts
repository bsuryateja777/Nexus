export interface Skill {
  skill_id: string
  agent_id: string
  name: string
  description: string
  parameters?: Record<string, unknown>
  aliases: string[]
}
