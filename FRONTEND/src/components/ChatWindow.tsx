import { useEffect, useRef } from 'react'
import { useChatContext } from '../context/ChatContext'
import Message from './Message'
import EmptyState from './EmptyState'
import Generating from './Generating'
import './ChatWindow.css'

interface ChatWindowProps {
  onActionSelect?: (prompt: string, skillId?: string) => void
}

export default function ChatWindow({ onActionSelect }: ChatWindowProps) {
  const { currentMessages, isLoading, isGenerating } = useChatContext()
  const endRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Only apply typing effect if isLoading is true (response is being generated)
  // AND it's a bot message that comes after the last user message
  const getIsLatestBotMessage = (index: number) => {
    if (!isLoading) return false

    const message = currentMessages[index]
    if (message.role !== 'bot') return false

    // Find the last user message
    const lastUserMessageIndex = currentMessages
      .map((msg, idx) => (msg.role === 'user' ? idx : -1))
      .reduce((last, current) => (current > last ? current : last), -1)

    // Apply typing effect only if:
    // 1. This is a bot message
    // 2. It comes after the last user message
    // 3. isLoading is true (meaning a response is currently being generated)
    if (lastUserMessageIndex >= 0) {
      // Get all bot messages after the last user message
      const botMessagesAfterUser = currentMessages
        .map((msg, idx) => (idx > lastUserMessageIndex && msg.role === 'bot' ? idx : -1))
        .filter(idx => idx !== -1)

      // Apply to the first (and usually only) bot message after the user message
      return index === botMessagesAfterUser[0]
    }

    return false
  }

  useEffect(() => {
    const timer = requestAnimationFrame(() => {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight
      }
    })
    return () => cancelAnimationFrame(timer)
  }, [currentMessages])

  return (
    <div className="chat-window" ref={containerRef}>
      {currentMessages.length === 0 ? (
        <EmptyState onActionSelect={onActionSelect} />
      ) : (
        <>
          {currentMessages.map((message, index) => (
            <Message
              key={message.id}
              message={message}
              isLatestBotMessage={getIsLatestBotMessage(index)}
            />
          ))}
          {isGenerating && <Generating />}
          <div ref={endRef} />
        </>
      )}
    </div>
  )
}
