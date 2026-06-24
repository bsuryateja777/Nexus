import { useState, useEffect, useRef } from 'react'
import { useChatContext } from '../context/ChatContext'
import CommandPalette from './CommandPalette'
import type { Skill } from '../types/Skill'
import './ChatInput.css'

interface ChatInputProps {
  suggestedPrompt?: string
  suggestedSkillId?: string
  onPromptUsed?: () => void
}

export default function ChatInput({ suggestedPrompt = '', suggestedSkillId, onPromptUsed }: ChatInputProps) {
  const [message, setMessage] = useState('')
  const [showPalette, setShowPalette] = useState(false)
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [prevMessage, setPrevMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { addMessage } = useChatContext()

  // Use suggested prompt if provided
  useEffect(() => {
    if (suggestedPrompt) {
      setMessage(suggestedPrompt)
      if (suggestedSkillId) {
        // Find and select the skill if skillId is provided
        // For now, we'll just note it in the state
      }
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
  }, [suggestedPrompt, suggestedSkillId])

  // Detect "/" in input - open palette only when "/" is first typed
  useEffect(() => {
    // Only open palette if message starts with "/" AND previous message didn't
    // This prevents reopening when just navigating with backspace
    if (message.startsWith('/') && !prevMessage.startsWith('/') && !showPalette) {
      setShowPalette(true)
    }
    setPrevMessage(message)
  }, [message, showPalette])


  // Focus input when palette closes
  useEffect(() => {
    if (!showPalette) {
      setTimeout(() => textareaRef.current?.focus(), 0)
    }
  }, [showPalette])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim()) {
      addMessage(message, {
        skill_id: selectedSkill?.skill_id,
        parameters: selectedSkill?.parameters || {}
      })
      setMessage('')
      setSelectedSkill(null)
      onPromptUsed?.()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as any)
    }
  }

  const handleSelectSkill = (skill: Skill) => {
    setSelectedSkill(skill)
    setMessage('')
    // Focus textarea after skill selection
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  const handleTogglePalette = () => {
    setShowPalette(!showPalette)
    if (!showPalette) {
      setMessage('/')
    }
  }

  return (
    <div className="chat-input-container">
      <CommandPalette
        isOpen={showPalette}
        onClose={(skillSelected) => {
          setShowPalette(false)
          // If no skill was selected and palette was closed (ESC/click outside)
          if (!skillSelected) {
            // Clear the "/" if it was just opened with /
            if (message.startsWith('/')) {
              setMessage(message.slice(1).trimStart())
            }
            // Clear skill if user pressed ESC while changing skill
            if (selectedSkill) {
              setSelectedSkill(null)
            }
          }
        }}
        onSelectSkill={handleSelectSkill}
      />

      <form onSubmit={handleSubmit} className="chat-input-form">
        <div className="chat-input-wrapper">
          {selectedSkill ? (
            <button
              type="button"
              className="skill-button skill-button-active"
              onClick={() => {
                setShowPalette(true)
              }}
              title="Click to change skill"
            >
              /{selectedSkill.skill_id}
            </button>
          ) : (
            <button
              type="button"
              className="skill-button"
              onClick={handleTogglePalette}
              title="Browse available skills"
            >
              /
            </button>
          )}

          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type '/' for skills or ask anything... (Shift+Enter for new line)"
            className="chat-input-field"
            rows={1}
            style={{ minHeight: '44px', maxHeight: '120px' }}
          />

          <button
            type="submit"
            disabled={!message.trim()}
            className="chat-input-button"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
