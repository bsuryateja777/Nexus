import { useState } from 'react'
import './SidebarSection.css'

interface SidebarSectionProps {
  title: string
  items: Array<{ id: string; label: string }>
  onItemClick?: (id: string) => void
  defaultExpanded?: boolean
}

export default function SidebarSection({
  title,
  items,
  onItemClick,
  defaultExpanded = true,
}: SidebarSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  return (
    <div className="sidebar-section">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="sidebar-section-header w-full"
      >
        <span className="sidebar-section-title">{title}</span>
        <span className="sidebar-section-toggle">
          {isExpanded ? '▼' : '▶'}
        </span>
      </button>

      {isExpanded && (
        <div className="sidebar-section-content">
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => onItemClick?.(item.id)}
              className="sidebar-section-item w-full text-left"
              title={item.label}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
