import { app, BrowserWindow, shell, ipcMain } from 'electron'
import { fileURLToPath } from 'url'
import path from 'path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

/**
 * Open something outside the app window: web URLs in the default browser,
 * local files (PDFs etc.) with the OS default handler.
 */
function openOutside(url: string) {
  try {
    if (/^https?:\/\//i.test(url)) {
      void shell.openExternal(url)
    } else if (url.startsWith('file://')) {
      void shell.openPath(fileURLToPath(url))
    } else if (/^[a-zA-Z]:[\\/]/.test(url) || url.startsWith('/')) {
      void shell.openPath(url)
    }
  } catch (err) {
    console.error('openOutside failed:', url, err)
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hiddenInset',
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '../public/icon.png'),
    show: false,
  })

  win.once('ready-to-show', () => {
    win.show()
    if (isDev) win.webContents.openDevTools({ mode: 'detach' })
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    openOutside(url)
    return { action: 'deny' }
  })

  // The window is frameless (no back button / address bar). If a link inside
  // the app (e.g. a PDF URL in a result) navigates this window, the whole
  // chat UI gets replaced and the user is stuck. Block all non-app navigation
  // and open those URLs externally instead.
  win.webContents.on('will-navigate', (event, url) => {
    const inApp = isDev && (url.startsWith('http://localhost:5173') || url.startsWith('http://127.0.0.1:5173'))
    if (!inApp) {
      event.preventDefault()
      openOutside(url)
    }
  })

  if (isDev) {
    win.loadURL('http://localhost:5173')
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

// Renderer-initiated opens (markdown links, file paths in results).
ipcMain.handle('app:open-external', (_event, url: unknown) => {
  if (typeof url === 'string' && /^https?:\/\//i.test(url)) return shell.openExternal(url)
  return null
})
ipcMain.handle('app:open-path', (_event, filePath: unknown) => {
  if (typeof filePath !== 'string') return null
  if (filePath.startsWith('file://')) return shell.openPath(fileURLToPath(filePath))
  if (/^[a-zA-Z]:[\\/]/.test(filePath) || filePath.startsWith('/')) return shell.openPath(filePath)
  return null
})

app.whenReady().then(() => {
  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
