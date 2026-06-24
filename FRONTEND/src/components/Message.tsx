import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useChatContext } from '../context/ChatContext'
import { useTypingEffect } from '../hooks/useTypingEffect'
import type { Message as MessageType } from '../context/ChatContext'
import './Message.css'

// Custom link component to open in new tab
const LinkComponent = (props: any) => {
  return (
    <a {...props} target="_blank" rel="noopener noreferrer" />
  )
}

interface MessageProps {
  message: MessageType
  isLatestBotMessage?: boolean
}

export default function Message({ message, isLatestBotMessage = false }: MessageProps) {
  const [copied, setCopied] = useState(false)
  const { regenerateMessage } = useChatContext()
  const { displayedText, isComplete } = useTypingEffect(
    message.role === 'bot' && isLatestBotMessage ? message.content : '',
    30
  )

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleRegenerate = () => {
    if (message.role === 'bot') {
      regenerateMessage()
    }
  }

  const timeStr = message.timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  const servicelinks = message.metadata?.servicelinks || []

  return (
    <div className={`message group ${message.role}`}>
      <div className="flex flex-col gap-1">
        <div className="message-content">
          <div className="message-text">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{ a: LinkComponent }}
            >
              {message.role === 'bot' && isLatestBotMessage ? displayedText : message.content}
            </ReactMarkdown>
          </div>
          {servicelinks.length > 0 && (isComplete || !isLatestBotMessage) && (
            <div className="servicelinks-section">
              <div className="servicelinks-header">Related Documentation</div>
              <div className="servicelinks-list">
                {servicelinks.map((link, idx) => (
                  <a
                    key={idx}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="servicelink-item"
                    title={link.description || link.title}
                  >
                    <span className="servicelink-title">{link.title}</span>
                    <div className="servicelink-badges">
                      {link.platform && (
                        <span className={`servicelink-platform servicelink-platform-${link.platform.toLowerCase()}`}>
                          {link.platform}
                        </span>
                      )}
                      {link.category && <span className="servicelink-category">{link.category}</span>}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="message-time">{timeStr}</span>
          <div className="message-actions">
            <button
              onClick={handleCopy}
              className="action-button"
              title="Copy message"
            >
              {copied ? '✓' : '📋'}
            </button>
            {message.role === 'bot' && (
              <button
                onClick={handleRegenerate}
                className="action-button"
                title="Regenerate response"
              >
                🔄
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
