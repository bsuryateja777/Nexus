import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ChatPage from './components/ChatPage'

function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/chat/:sessionId" element={<ChatPage />} />
        <Route path="/chat" element={<Navigate to="/chat/new" replace />} />
        <Route path="/" element={<Navigate to="/chat/new" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
