import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useChatContext } from '../context/ChatContext'
import type { Conversation } from '../context/ChatContext'
import './ConversationItem.css'

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  isCollapsed: boolean
  isFavorite?: boolean
  onToggleFavorite?: (id: string) => void
  showPreview?: boolean
}

export default function ConversationItem({
  conversation,
  isActive,
  isCollapsed,
  isFavorite = false,
  onToggleFavorite,
  showPreview = true,
}: ConversationItemProps) {
  const navigate = useNavigate()
  const [isRenaming, setIsRenaming] = useState(false)
  const [newTitle, setNewTitle] = useState(conversation.title)
  const [menuOpen, setMenuOpen] = useState(false)
  const {
    selectConversation,
    renameConversation,
    deleteConversation,
  } = useChatContext()

  // Sync local state when conversation title changes
  useEffect(() => {
    setNewTitle(conversation.title)
  }, [conversation.title])

  const messages = conversation.messages || []
  const preview =
    messages[messages.length - 1]?.content ||
    'No messages yet'

  const handleRename = async () => {
    if (newTitle.trim()) {
      await renameConversation(conversation.id, newTitle.trim())
      setIsRenaming(false)
    }
  }

  if (isRenaming) {
    return (
      <div className="conversation-item group">
        <input
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onBlur={handleRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleRename()
            if (e.key === 'Escape') setIsRenaming(false)
          }}
          className="rename-input"
          autoFocus
        />
      </div>
    )
  }

  return (
    <div
      className={`conversation-item group ${isActive ? 'active' : ''}`}
      onClick={() => {
        selectConversation(conversation.id)
        navigate(`/chat/${conversation.id}`)
      }}
      title={isCollapsed ? conversation.title : ''}
    >
      {!isCollapsed && (
        <>
          <div
            className="conversation-title"
            onDoubleClick={(e) => {
              e.stopPropagation()
              setIsRenaming(true)
            }}
          >
            {conversation.title}
          </div>
          {showPreview && (
            <div className="conversation-preview">{preview.substring(0, 40)}...</div>
          )}
        </>
      )}
      {!isCollapsed && (
        <div className="conversation-menu-wrapper">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setMenuOpen(!menuOpen)
            }}
            className="conversation-menu-button"
            title="More options"
          >
            ⋯
          </button>
          {menuOpen && (
            <div className="conversation-menu">
              <button
                className="conversation-menu-item"
                onClick={(e) => {
                  e.stopPropagation()
                  onToggleFavorite?.(conversation.id)
                  setMenuOpen(false)
                }}
              >
                {isFavorite ? '★ Remove from favorites' : '☆ Add to favorites'}
              </button>
              <button
                className="conversation-menu-item"
                onClick={(e) => {
                  e.stopPropagation()
                  setIsRenaming(true)
                  setMenuOpen(false)
                }}
              >
                ✎ Rename
              </button>
              <div className="conversation-menu-divider" />
              <button
                className="conversation-menu-item conversation-menu-delete"
                onClick={(e) => {
                  e.stopPropagation()
                  deleteConversation(conversation.id)
                  setMenuOpen(false)
                  navigate('/chat/new')
                }}
              >
                🗑️ Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
