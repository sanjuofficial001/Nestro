# Scripts

Shared repository tooling for Nestro: database migrations, seed/fixture runners, code generation, and deploy helpers.

Scripts are intentionally stateless and idempotent where possible. Each script documents its prerequisites and expected inputs at the top of the file. They are the only place repo-level automation lives; app- and backend-specific tasks belong in their own workspaces.
