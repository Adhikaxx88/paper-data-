import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import { ChatWindow } from './components/ChatWindow'
import { InputBar } from './components/InputBar'

function App() {
  const { sessionId } = useSession()
  const { messages, isLoading, sendMessage } = useChat(sessionId)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="fixed inset-x-0 top-0 z-10 border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-2xl px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">NewsRAG</h1>
        </div>
      </header>

      <main className="min-h-screen pt-16 pb-0">
        <ChatWindow messages={messages} isLoading={isLoading} />
      </main>

      <InputBar onSend={sendMessage} isLoading={isLoading} />
    </div>
  )
}

export default App
