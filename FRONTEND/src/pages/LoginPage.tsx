import React, { useEffect } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

export function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    // If already authenticated, redirect to home
    if (isAuthenticated) {
      navigate("/", { replace: true })
      return
    }

    // Trigger login
    login().catch(error => {
    })
  }, [isAuthenticated, navigate, login])

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Assistant</h1>
        <p className="text-xl text-gray-600 mb-8">Redirecting to login...</p>
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-accent"></div>
      </div>
    </div>
  )
}
