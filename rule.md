u cant change any existing features or functionalities , only add or modify features as per user request and then tell everything what u have modify
whenever anything new u want to create then look for existig codes
codes should be have good modularity 
ensure good variable namigs to the features one function is used for one task properly
dont change anything in existing just see and ask for me if there is need for any changes
everything u have to check before making changes
behave like u are senior software developer

approved changes:
- User-requested features may be added after inspecting the existing implementation.
- Existing public routes and behavior must remain compatible unless the user explicitly asks for a breaking change.
- New backend code must use domain folders, one responsibility per function, descriptive names, and dependency injection.
- Backend files use kebab-case names: `feature.controller.ts`, `feature.service.ts`, and `feature.module.ts`.
- Classes use PascalCase; functions and variables use camelCase; constants use UPPER_SNAKE_CASE.
- Middleware belongs in `backend/src/common/middleware/` and must be registered through a module.
- Environment values must come from configuration; secrets must never be committed.
- Before edits, inspect related files. After edits, run focused diagnostics or tests and report every modification.