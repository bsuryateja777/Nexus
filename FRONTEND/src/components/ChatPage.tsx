import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { ChatProvider } from '../context/ChatContext'
import { ThemeProvider } from '../context/ThemeContext'
import Sidebar from './Sidebar'
import ChatWindow from './ChatWindow'
import ChatInput from './ChatInput'
import './ChatPage.css'

function ChatPageContent() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [suggestedPrompt, setSuggestedPrompt] = useState('')
  const [suggestedSkillId, setSuggestedSkillId] = useState<string | undefined>()

  const handleToggleSidebar = () => {
    setSidebarOpen(!sidebarOpen)
  }

  const handleActionSelect = (prompt: string, skillId?: string) => {
    setSuggestedPrompt(prompt)
    setSuggestedSkillId(skillId)
  }

  return (
    <div className="chat-page">
      {/* Desktop Sidebar */}
      <div
        className="chat-sidebar-wrapper"
        onMouseEnter={() => setSidebarOpen(true)}
        onMouseLeave={() => setSidebarOpen(false)}
      >
        <Sidebar isCollapsed={!sidebarOpen} onToggleSidebar={handleToggleSidebar} />
      </div>

      {/* Mobile Sidebar Overlay */}
      {mobileOpen && (
        <div
          className="chat-mobile-overlay md:hidden z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}
      {mobileOpen && (
        <div className="chat-sidebar-mobile">
          <button
            onClick={() => setMobileOpen(false)}
            className="chat-close-button"
          >
            ✕
          </button>
          <Sidebar isCollapsed={!sidebarOpen} onToggleSidebar={handleToggleSidebar} />
        </div>
      )}

      {/* Main Chat Area */}
      <div className="chat-main">
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="chat-mobile-button"
        >
          ☰
        </button>
        <div className="chat-content">
          <ChatWindow onActionSelect={handleActionSelect} />
          <ChatInput suggestedPrompt={suggestedPrompt} suggestedSkillId={suggestedSkillId} onPromptUsed={() => { setSuggestedPrompt(''); setSuggestedSkillId(undefined) }} />
        </div>
      </div>
    </div>
  )
}

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId: string }>()

  return (
    <ThemeProvider>
      <ChatProvider initialSessionId={sessionId}>
        <ChatPageContent />
      </ChatProvider>
    </ThemeProvider>
  )
}
