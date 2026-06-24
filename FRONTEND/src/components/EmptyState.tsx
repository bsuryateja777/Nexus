import './EmptyState.css'

interface EmptyStateProps {
  onActionSelect?: (prompt: string, skillId?: string) => void
}

export default function EmptyState({ onActionSelect }: EmptyStateProps) {

  const handleAction = (prompt: string, skillId?: string) => {
    if (onActionSelect) {
      onActionSelect(prompt, skillId)
    }
  }

  return (
    <div className="empty-state">
      <div className="empty-state-icon">✨</div>
      <h1 className="empty-state-title">What can I help you with?</h1>
      <div className="empty-state-actions">
        <button
          className="empty-state-button"
          onClick={() => handleAction('Help me write or edit this: ', 'claude')}
          title="General writing and editing assistance"
        >
          <span className="empty-state-button-icon">✍️</span>
          Write or edit
        </button>
        <button
          className="empty-state-button"
          onClick={() => handleAction('/knowledge ', 'knowledge')}
          title="Search knowledge base"
        >
          <span className="empty-state-button-icon">🔍</span>
          Search knowledge
        </button>
        <button
          className="empty-state-button"
          onClick={() => handleAction('/azure ', 'azure')}
          title="Execute Azure operations"
        >
          <span className="empty-state-button-icon">☁️</span>
          Azure operations
        </button>
      </div>
    </div>
  )
}
