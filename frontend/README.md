# Naukar Frontend Workspace

Frontend workspace for Naukar monorepo.

## Stack

- Electron
- React 18
- TypeScript
- Vite
- Zustand

## Run Commands

Run all commands from repository root:

```powershell
# Install workspace dependencies
"C:\Program Files\nodejs\corepack.cmd" yarn install

# Frontend web mode (recommended)
"C:\Program Files\nodejs\corepack.cmd" yarn dev:web

# Frontend Electron mode
"C:\Program Files\nodejs\corepack.cmd" yarn dev:frontend

# Build
"C:\Program Files\nodejs\corepack.cmd" yarn build

# Type check
"C:\Program Files\nodejs\corepack.cmd" yarn typecheck
```

## Direct Workspace Commands

```powershell
"C:\Program Files\nodejs\corepack.cmd" yarn workspace @naukar/frontend dev:vite
"C:\Program Files\nodejs\corepack.cmd" yarn workspace @naukar/frontend dev
"C:\Program Files\nodejs\corepack.cmd" yarn workspace @naukar/frontend build
"C:\Program Files\nodejs\corepack.cmd" yarn workspace @naukar/frontend typecheck
```

## Notes

- Web mode is more stable for day-to-day development.
- Electron mode depends on local desktop runtime and may fail if Electron prerequisites are missing.
