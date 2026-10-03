import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
    // Bind-mounting a Windows drive (/mnt/c/...) through WSL2 into a Docker
    // container drops inotify events, so chokidar's default watcher never
    // fires on host edits and Vite keeps serving stale in-memory transforms
    // even though the file on disk is current. Polling forces it to notice.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
})
