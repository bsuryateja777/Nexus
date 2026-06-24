import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import './UserProfile.css'

interface UserProfileProps {
  isCollapsed?: boolean
}

export default function UserProfile({ isCollapsed = false }: UserProfileProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { user, isAuthenticated, login, logout } = useAuth()

  if (!isAuthenticated || !user) {
    return (
      <div className={`user-profile ${isCollapsed ? 'collapsed' : ''}`}>
        <button
          onClick={() => login()}
          className="user-avatar"
          title="Login"
          style={{ fontSize: '18px' }}
        >
          🔐
        </button>

        {!isCollapsed && (
          <button
            onClick={() => login()}
            className="user-info"
            style={{ cursor: 'pointer', border: 'none', background: 'none', width: '100%', textAlign: 'left' }}
          >
            <div className="user-name">Not signed in</div>
            <div className="user-email" style={{ fontSize: '12px' }}>Click to login</div>
          </button>
        )}
      </div>
    )
  }

  const initials = user.name
    .split(' ')
    .map((n: string) => n[0])
    .join('')
    .toUpperCase()

  return (
    <div className={`user-profile ${isCollapsed ? 'collapsed' : ''}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="user-avatar"
        title={user.name}
      >
        {initials}
      </button>

      {!isCollapsed && (
        <div className="user-info" onClick={() => setIsOpen(!isOpen)}>
          <div className="user-name">{user.name}</div>
          <div className="user-email">{user.email}</div>
        </div>
      )}

      {isOpen && (
        <>
          <div
            className="fixed inset-0"
            onClick={() => setIsOpen(false)}
          />
          <div className="user-dropdown">
            <div className="user-dropdown-header">
              <div className="font-semibold">{user.name}</div>
              <div className="user-dropdown-email">{user.email}</div>
            </div>

            <button className="user-dropdown-item">
              👤 View Profile
            </button>
            <button className="user-dropdown-item">
              ⚙️ Settings
            </button>

            <div className="user-dropdown-divider" />

            <button
              onClick={() => {
                setIsOpen(false)
                logout()
              }}
              className="user-dropdown-item user-dropdown-logout"
            >
              🚪 Logout
            </button>
          </div>
        </>
      )}
    </div>
  )
}
