import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useChatContext } from '../context/ChatContext'
import UserProfile from './UserProfile'
import ConversationItem from './ConversationItem'
import './Sidebar.css'

interface SidebarProps {
  isCollapsed: boolean
  onToggleSidebar: () => void
}

export default function Sidebar({ isCollapsed, onToggleSidebar }: SidebarProps) {
  const navigate = useNavigate()
  const {
    conversations,
    addConversation,
    deleteConversation,
  } = useChatContext()
  const [searchQuery, setSearchQuery] = useState('')
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleNewChat = () => {
    if (isCollapsed) {
      onToggleSidebar()
    }
    const newSessionId = addConversation('New Conversation')
    navigate(`/chat/${newSessionId}`)
  }

  const toggleFavorite = (id: string) => {
    const newFavorites = new Set(favorites)
    if (newFavorites.has(id)) {
      newFavorites.delete(id)
    } else {
      newFavorites.add(id)
    }
    setFavorites(newFavorites)
  }

  const handleDeleteAllHistory = async () => {
    setShowDeleteConfirm(false)
    for (const conversation of conversations) {
      await deleteConversation(conversation.id)
    }
    navigate('/')
  }

  const filteredConversations =
    searchQuery.length > 0
      ? conversations.filter(
          (c) =>
            c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            c.messages.some((m) =>
              m.content.toLowerCase().includes(searchQuery.toLowerCase())
            )
        )
      : conversations

  const favoriteConversations = conversations.filter((c) =>
    favorites.has(c.id)
  )

  const recentConversations = conversations

  return (
    <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Logo */}
      <div className="sidebar-header">
        {!isCollapsed && (
          <div className="sidebar-logo">
            <h2>SDC Assistant</h2>
          </div>
        )}
        {isCollapsed && (
          <div className="sidebar-logo-collapsed">
            <span>SDC</span>
          </div>
        )}
      </div>

      {/* New Chat Button */}
      <div className="sidebar-new-chat">
        <button onClick={handleNewChat} className="new-chat-btn">
          <span className="btn-icon">+</span>
          {!isCollapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* Search */}
      {isCollapsed && (
        <button
          onClick={() => onToggleSidebar()}
          className="search-icon-button"
          title="Search chats"
        >
          <svg
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <circle cx="10" cy="10" r="6" />
            <line x1="14" y1="14" x2="20" y2="20" />
          </svg>
        </button>
      )}
      {!isCollapsed && (
        <div className="sidebar-search">
          <input
            type="text"
            placeholder="Search chats"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                onToggleSidebar()
              }
            }}
            className="search-input"
            autoFocus
          />
        </div>
      )}

      {/* Scrollable Content */}
      <div className="sidebar-content">
        {/* When searching: show filtered results */}
        {searchQuery && !isCollapsed && (
          <>
            {filteredConversations.length > 0 ? (
              <div className="sidebar-section">
                <div className="sidebar-section-header">
                  <span className="sidebar-section-title">Search Results</span>
                </div>
                <div className="sidebar-section-content">
                  {filteredConversations.map((conv) => (
                    <ConversationItem
                      key={conv.id}
                      conversation={conv}
                      isActive={false}
                      isCollapsed={isCollapsed}
                      isFavorite={favorites.has(conv.id)}
                      onToggleFavorite={toggleFavorite}
                      showPreview={false}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className="sidebar-no-results">
                No results found
              </div>
            )}
          </>
        )}

        {/* When not searching: show Favorites and Recents */}
        {!searchQuery && !isCollapsed && (
          <>
            {/* Favorites Section */}
            {favoriteConversations.length > 0 && (
              <div className="sidebar-section">
                <div className="sidebar-section-header">
                  <span className="sidebar-section-title">Favorites</span>
                </div>
                <div className="sidebar-section-content">
                  {favoriteConversations.map((conv) => (
                    <ConversationItem
                      key={conv.id}
                      conversation={conv}
                      isActive={false}
                      isCollapsed={isCollapsed}
                      isFavorite={favorites.has(conv.id)}
                      onToggleFavorite={toggleFavorite}
                      showPreview={false}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Recents Section */}
            <div className="sidebar-section">
              <div className="sidebar-section-header">
                <div className="sidebar-section-header-content">
                  <span className="sidebar-section-title">Recents</span>
                  {conversations.length > 0 && (
                    <button
                      onClick={() => setShowDeleteConfirm(true)}
                      className="delete-all-btn"
                      title="Delete all chat history"
                    >
                      Clear All
                    </button>
                  )}
                </div>
              </div>
              <div className="sidebar-section-content">
                {recentConversations.map((conv) => (
                  <ConversationItem
                    key={conv.id}
                    conversation={conv}
                    isActive={false}
                    isCollapsed={isCollapsed}
                    isFavorite={favorites.has(conv.id)}
                    onToggleFavorite={toggleFavorite}
                    showPreview={false}
                  />
                ))}
              </div>
            </div>
          </>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteConfirm && (
          <div className="delete-confirm-overlay">
            <div className="delete-confirm-modal">
              <h3>Delete All Chat History?</h3>
              <p>This action cannot be undone. All conversations will be permanently deleted.</p>
              <div className="delete-confirm-buttons">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="delete-confirm-cancel"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteAllHistory}
                  className="delete-confirm-delete"
                >
                  Delete All
                </button>
              </div>
            </div>
          </div>
        )}

      </div>

      {/* User Profile Footer */}
      <div className="sidebar-footer">
        <UserProfile isCollapsed={isCollapsed} />
      </div>
    </div>
  )
}
