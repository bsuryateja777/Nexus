import { createContext, useContext, useState, useEffect, type ReactNode } from "react"
import { msalInstance, loginRequest } from "../lib/authConfig"

interface User {
  id: string
  email: string
  name: string
}

interface AuthContextType {
  user: User | null
  accessToken: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: () => Promise<void>
  logout: () => Promise<void>
  getAccessToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [msalReady, setMsalReady] = useState(false)

  // Check if auth is enabled (VITE_ENTRA_CLIENT_ID set)
  const authEnabled = !!import.meta.env.VITE_ENTRA_CLIENT_ID

  // Initialize MSAL on mount
  useEffect(() => {
    const initMsal = async () => {
      try {
        if (!authEnabled) {
          // Auth disabled - set guest user
          setUser({
            id: "guest",
            email: "guest@localhost",
            name: "Guest User"
          })
          setAccessToken("guest-token")
          setMsalReady(true)
          return
        }

        // Initialize MSAL instance
        await msalInstance.initialize()

        // Handle redirect from Entra ID
        await msalInstance.handleRedirectPromise()

        setMsalReady(true)
      } catch (error) {
        setMsalReady(true) // Set to true anyway to avoid infinite loop
      }
    }

    initMsal()
  }, [authEnabled])

  // Initialize auth on mount (after MSAL is ready)
  useEffect(() => {
    if (!msalReady) return

    const initializeAuth = async () => {
      try {
        // Check if user is already logged in
        const accounts = msalInstance.getAllAccounts()

        if (accounts && accounts.length > 0) {
          const account = accounts[0]
          setUser({
            id: account.homeAccountId,
            email: account.username || "",
            name: account.name || ""
          })

          // Try to get access token silently
          try {
            const response = await msalInstance.acquireTokenSilent({
              scopes: loginRequest.scopes,
              account: account
            })
            setAccessToken(response.accessToken)
          } catch (error) {
            // Token refresh failed, user may need to re-login
            setAccessToken(null)
          }
        }
      } catch (error) {
      } finally {
        setIsLoading(false)
      }
    }

    initializeAuth()
  }, [msalReady])

  const login = async () => {
    try {
      setIsLoading(true)

      if (!authEnabled) {
        // Auth disabled - already logged in as guest
        return
      }

      const response = await msalInstance.loginPopup(loginRequest)

      if (response && response.account) {
        setUser({
          id: response.account.homeAccountId,
          email: response.account.username || "",
          name: response.account.name || ""
        })

        setAccessToken(response.accessToken)
      }
    } catch (error) {
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      setIsLoading(true)

      if (!authEnabled) {
        // Auth disabled - nothing to do
        return
      }

      await msalInstance.logoutPopup({
        postLogoutRedirectUri: "/",
        mainWindowRedirectUri: "/"
      })

      setUser(null)
      setAccessToken(null)
    } catch (error) {
      // Clear local state even if logout fails
      setUser(null)
      setAccessToken(null)
    } finally {
      setIsLoading(false)
    }
  }

  const getAccessToken = async (): Promise<string | null> => {
    try {
      if (!authEnabled) {
        // Auth disabled - return guest token
        return "guest-token"
      }

      const accounts = msalInstance.getAllAccounts()

      if (!accounts || accounts.length === 0) {
        return null
      }

      const account = accounts[0]

      // Try silent token acquisition first
      try {
        const response = await msalInstance.acquireTokenSilent({
          scopes: loginRequest.scopes,
          account: account
        })
        return response.accessToken
      } catch (error) {
        // If silent acquisition fails, try popup
        const response = await msalInstance.acquireTokenPopup({
          scopes: loginRequest.scopes,
          account: account
        })
        return response.accessToken
      }
    } catch (error) {
      return null
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        getAccessToken
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider")
  }
  return context
}
