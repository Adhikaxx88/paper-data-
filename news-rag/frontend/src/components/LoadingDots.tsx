export function LoadingDots() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce-dot" style={{ animationDelay: '0ms' }} />
      <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce-dot" style={{ animationDelay: '150ms' }} />
      <span className="h-2 w-2 rounded-full bg-gray-400 animate-bounce-dot" style={{ animationDelay: '300ms' }} />
    </div>
  )
}
