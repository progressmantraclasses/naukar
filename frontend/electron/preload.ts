import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  isElectron: true,
  openExternal: (url: string) => ipcRenderer.invoke('app:open-external', url),
  openPath: (filePath: string) => ipcRenderer.invoke('app:open-path', filePath),
})

