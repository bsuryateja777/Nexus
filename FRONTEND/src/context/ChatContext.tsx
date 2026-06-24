import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from './AuthContext'

export interface Message {
  id: string
  role: 'user' | 'bot'
  content: string
  timestamp: Date
  metadata?: {
    servicelinks?: Array<{
      title: string
      url: string
      description?: string
      category?: string
    }>
    [key: string]: any
  }
}

export interface Conversation {
  id: string
  title: string
  messages: Message[]
  createdAt: Date
}

export interface User {
  id: string
  name: string
  email: string
  avatar?: string
}

interface ChatContextType {
  conversations: Conversation[]
  currentConversationId: string | null
  currentMessages: Message[]
  currentUser: User
  isLoading: boolean
  isGenerating: boolean
  addConversation: (title: string) => string
  deleteConversation: (id: string) => Promise<void>
  renameConversation: (id: string, newTitle: string) => void
  selectConversation: (id: string) => void
  addMessage: (content: string, skillOptions?: { skill_id?: string; parameters?: Record<string, unknown> }) => Promise<void>
  regenerateMessage: () => void
  searchConversations: (query: string) => Conversation[]
}

const ChatContext = createContext<ChatContextType | undefined>(undefined)


const botResponses = [
  "That's a great question! Let me break that down for you.",
  "I can help you with that. In essence, it works like this: ",
  "Good thinking! Here's what I'd recommend: ",
  "Interesting point. Let me share some insights: ",
  "That's something I've seen asked before. The answer is: ",
]

interface ChatProviderProps {
  children: ReactNode
  initialSessionId?: string
}

export const ChatProvider = ({ children, initialSessionId }: ChatProviderProps) => {
  const { accessToken, user: authUser } = useAuth()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(
    initialSessionId && initialSessionId !== 'new' ? initialSessionId : null
  )
  const [currentMessages, setCurrentMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isLoadingConversations, setIsLoadingConversations] = useState(true)

  // Create user object from auth context
  const currentUser: User = authUser ? {
    id: authUser.id,
    name: authUser.name,
    email: authUser.email,
  } : {
    id: 'guest',
    name: 'Guest',
    email: 'guest@example.com',
  }

  // Fetch conversations from backend on auth ready
  useEffect(() => {
    const fetchConversations = async () => {
      if (!accessToken) {
        setIsLoadingConversations(false)
        return
      }

      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        const response = await fetch(`${apiUrl}/chat/conversations`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        })

        if (response.ok) {
          const data = await response.json()
          const convList = data.conversations || []
          // Ensure each conversation has a messages array (required for updates)
          const conversationsWithMessages = convList.map((conv: any) => ({
            ...conv,
            messages: conv.messages || [],
            createdAt: new Date(conv.created_at || Date.now()),
            updatedAt: new Date(conv.updated_at || Date.now())
          }))
          setConversations(conversationsWithMessages)

          // Set current conversation to first one if available
          if (conversationsWithMessages.length > 0) {
            setCurrentConversationId(conversationsWithMessages[0].id)
          }
        } else {
        }
      } catch (error) {
      } finally {
        setIsLoadingConversations(false)
      }
    }

    fetchConversations()
  }, [accessToken])

  // Fetch messages for current conversation
  useEffect(() => {
    const fetchMessages = async () => {
      if (!accessToken || !currentConversationId) {
        setCurrentMessages([])
        return
      }

      try {
        const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        const response = await fetch(
          `${apiUrl}/chat/history?session_id=${currentConversationId}`,
          {
            headers: {
              'Authorization': `Bearer ${accessToken}`
            }
          }
        )

        if (response.ok) {
          const data = await response.json()
          const messages = data.messages || []
          // Convert to Message format
          const formattedMessages: Message[] = messages.map((m: any) => ({
            id: m.id,
            role: m.role === 'assistant' ? 'bot' : m.role,
            content: m.content,
            timestamp: new Date(m.created_at || Date.now()),
            metadata: m.metadata
          }))
          setCurrentMessages(formattedMessages)
        }
      } catch (error) {
      }
    }

    fetchMessages()
  }, [accessToken, currentConversationId])

  const addConversation = (title: string) => {
    const newId = Date.now().toString()
    const newConversation: Conversation = {
      id: newId,
      title,
      messages: [],
      createdAt: new Date(),
    }
    // Optimistically add to UI
    setConversations([newConversation, ...conversations])
    setCurrentConversationId(newId)
    setCurrentMessages([])
    return newId
  }

  const deleteConversation = async (id: string) => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/chat/clear?session_id=${id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      })

      // Delete from UI regardless of backend response (handles empty conversations that exist only in frontend)
      setConversations(conversations.filter((c) => c.id !== id))
      if (currentConversationId === id) {
        const remaining = conversations.filter((c) => c.id !== id)
        setCurrentConversationId(remaining[0]?.id || null)
        setCurrentMessages([])
      }

      if (!response.ok) {
      }
    } catch (error) {
    }
  }

  const renameConversation = async (id: string, newTitle: string): Promise<void> => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/chat/rename?session_id=${id}&new_title=${encodeURIComponent(newTitle)}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      })


      if (response.ok) {
        // Update UI with renamed conversation (use functional setState)
        setConversations((prev) => {
          const updated = prev.map((c) => {
            if (c.id === id) {
              return { ...c, title: newTitle }
            }
            return c
          })
          return updated
        })
      } else {
        const errorText = await response.text()
      }
    } catch (error) {
    }
  }

  const selectConversation = (id: string) => {
    setCurrentConversationId(id)
    // Messages will be fetched by useEffect
  }

  const addMessage = async (
    content: string,
    skillOptions?: { skill_id?: string; parameters?: Record<string, unknown> }
  ) => {
    // If no conversation exists, create one with current timestamp
    const sessionId = currentConversationId || Date.now().toString()
    const isNewConversation = !currentConversationId

    // If we generated a new ID, update state
    if (isNewConversation) {
      setCurrentConversationId(sessionId)
      setCurrentMessages([])
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    }

    // For new conversations, immediately add user message to display
    if (isNewConversation) {
      setCurrentMessages([userMessage])
    }

    setConversations((prevConversations) => {
      const updated = prevConversations.map((conv) => {
        if (conv.id === sessionId) {
          return {
            ...conv,
            messages: [...conv.messages, userMessage],
          }
        }
        return conv
      })

      // If conversation doesn't exist yet, create it
      if (!updated.some(c => c.id === sessionId)) {
        return [
          {
            id: sessionId,
            title: "New Conversation",
            messages: [userMessage],
            createdAt: new Date()
          },
          ...updated
        ]
      }

      return updated
    })

    // Update currentMessages with user message (for existing conversations, append it)
    if (!isNewConversation) {
      setCurrentMessages((prev) => [...prev, userMessage])
    }

    setIsGenerating(true)
    setIsLoading(true)

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

      // Call backend API with skill metadata and auth token
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }

      // Include Bearer token if available
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`
      }

      const response = await fetch(`${apiUrl}/chat/message?session_id=${sessionId}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          content,
          skill_id: skillOptions?.skill_id,
          parameters: skillOptions?.parameters || {},
        }),
      })

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`)
      }

      const data = await response.json()

      const botMessage: Message = {
        id: Date.now().toString(),
        role: 'bot',
        content: data.content,
        timestamp: new Date(),
        metadata: data.metadata
      }


      setConversations((prevConversations) => {
        return prevConversations.map((conv) => {
          if (conv.id === sessionId) {
            // If backend generated a title, use it (for new conversations)
            const updatedConv = {
              ...conv,
              messages: [...conv.messages, botMessage],
            }
            // Always apply generated title if provided by backend
            if (data.generated_title) {
              updatedConv.title = data.generated_title
            }
            return updatedConv
          }
          return conv
        })
      })

      // Immediately add bot message to currentMessages (don't wait for sync)
      setCurrentMessages((prev) => {
        const updated = [...prev, botMessage]
        return updated
      })

      // Stop generating animation as soon as bot message appears
      setIsGenerating(false)

      // Fetch updated conversation history from backend to sync state
      try {
        const historyResponse = await fetch(
          `${apiUrl}/chat/history?session_id=${sessionId}`,
          {
            headers: {
              'Authorization': `Bearer ${accessToken}`
            }
          }
        )

        if (historyResponse.ok) {
          const historyData = await historyResponse.json()
          const backendMessages = historyData.messages || []

          // Convert backend messages to frontend format
          const formattedMessages: Message[] = backendMessages.map((m: any) => ({
            id: m.id,
            role: m.role === 'assistant' ? 'bot' : m.role,
            content: m.content,
            timestamp: new Date(m.created_at || Date.now()),
            metadata: m.metadata
          }))

          // Update conversation in conversations list
          setConversations((prev) =>
            prev.map((conv) =>
              conv.id === sessionId
                ? { ...conv, messages: formattedMessages }
                : conv
            )
          )

          // Only sync currentMessages if they're out of sync with backend
          // This prevents race conditions from overwriting newer local messages
          setCurrentMessages((prevMessages) => {
            // If local messages match backend message count, keep local (it's fresher)
            if (prevMessages.length >= formattedMessages.length) {
              return prevMessages
            }
            // Otherwise, use backend as source of truth
            return formattedMessages
          })
        }
      } catch (error) {
      }

      // Keep isLoading true for typing effect duration (~3s for average message)
      setTimeout(() => {
        setIsLoading(false)
      }, 3000)
    } catch (error) {
      setIsGenerating(false)
      setIsLoading(false)

      // Show error message to user
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'bot',
        content: `Error: Failed to get response. ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      }

      setConversations((prevConversations) =>
        prevConversations.map((conv) => {
          if (conv.id === currentConversationId) {
            return {
              ...conv,
              messages: [...conv.messages, errorMessage],
            }
          }
          return conv
        })
      )
    }
  }

  const regenerateMessage = () => {
    if (!currentConversationId || currentMessages.length < 2) return

    setConversations((prevConversations) =>
      prevConversations.map((conv) => {
        if (conv.id === currentConversationId) {
          const messagesWithoutLastBot = conv.messages.slice(0, -1)
          const lastUserMessage =
            messagesWithoutLastBot[messagesWithoutLastBot.length - 1]

          if (lastUserMessage?.role !== 'user') return conv

          const newBotMessage: Message = {
            id: Date.now().toString(),
            role: 'bot',
            content:
              botResponses[
                Math.floor(Math.random() * botResponses.length)
              ] + ' ' + lastUserMessage.content.slice(0, 20) + '...',
            timestamp: new Date(),
          }

          return {
            ...conv,
            messages: [...messagesWithoutLastBot, newBotMessage],
          }
        }
        return conv
      })
    )
  }

  const searchConversations = (query: string) => {
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(query.toLowerCase()) ||
        c.messages.some((m) =>
          m.content.toLowerCase().includes(query.toLowerCase())
        )
    )
  }

  return (
    <ChatContext.Provider
      value={{
        conversations,
        currentConversationId: currentConversationId || null,
        currentMessages,
        currentUser,
        isLoading,
        isGenerating,
        addConversation,
        deleteConversation,
        renameConversation,
        selectConversation,
        addMessage,
        regenerateMessage,
        searchConversations,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export const useChatContext = () => {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error('useChatContext must be used within ChatProvider')
  }
  return context
}
