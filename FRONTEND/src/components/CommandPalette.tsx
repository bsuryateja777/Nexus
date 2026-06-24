import { useState, useEffect, useRef } from 'react'
import type { Skill } from '../types/Skill'
import './CommandPalette.css'

interface CommandPaletteProps {
  isOpen: boolean
  onClose: (skillSelected?: boolean) => void
  onSelectSkill: (skill: Skill) => void
}

export default function CommandPalette({
  isOpen,
  onClose,
  onSelectSkill
}: CommandPaletteProps) {
  const [searchTerm, setSearchTerm] = useState("")
  const [skills, setSkills] = useState<Skill[]>([])
  const [focusedIndex, setFocusedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Fetch skills on mount
  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        const response = await fetch(`${apiUrl}/agents`)
        if (response.ok) {
          const data = await response.json()
          setSkills(data)
        }
      } catch (error) {
      }
    }

    if (isOpen) {
      fetchSkills()
      // Focus input when opened
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [isOpen])

  // Handle Escape key globally
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    if (isOpen) {
      window.addEventListener('keydown', handleEscape, true)
      return () => window.removeEventListener('keydown', handleEscape, true)
    }
  }, [isOpen, onClose])

  const filtered = skills.filter(s =>
    s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    s.aliases.some(alias => alias.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  // Reset focused index when filtered results change
  useEffect(() => {
    setFocusedIndex(0)
  }, [searchTerm])

  const handleSelectSkill = (skill: Skill) => {
    onSelectSkill(skill)
    setSearchTerm("")
    onClose(true)
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusedIndex(prev => (prev + 1) % filtered.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusedIndex(prev => (prev - 1 + filtered.length) % filtered.length)
    } else if (e.key === 'Enter' && filtered.length > 0) {
      e.preventDefault()
      handleSelectSkill(filtered[focusedIndex])
    }
  }

  if (!isOpen) return null

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="command-palette" onClick={(e) => e.stopPropagation()}>
        <div className="command-palette-header">
          <input
            ref={inputRef}
            type="text"
            placeholder="Search skills..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={handleInputKeyDown}
            className="command-palette-input"
          />
          <button className="command-palette-close" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="command-palette-list">
          {filtered.length === 0 ? (
            <div className="command-palette-message">
              {skills.length === 0 ? 'No skills available' : 'No matching skills'}
            </div>
          ) : (
            filtered.map((skill, index) => (
              <button
                key={skill.skill_id}
                className={`command-palette-item ${index === focusedIndex ? 'focused' : ''}`}
                onClick={() => handleSelectSkill(skill)}
              >
                <div className="command-palette-item-name">
                  /{skill.skill_id}
                </div>
                <div className="command-palette-item-desc">
                  {skill.description}
                </div>
                {skill.aliases.length > 0 && (
                  <div className="command-palette-item-aliases">
                    Aliases: {skill.aliases.map(a => `/${a}`).join(', ')}
                  </div>
                )}
              </button>
            ))
          )}
        </div>

        <div className="command-palette-footer">
          <span className="command-palette-hint">
            Press <kbd>Esc</kbd> to close
          </span>
        </div>
      </div>
    </div>
  )
}
