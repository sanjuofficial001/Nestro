# Docker

Container and Compose definitions for running Nestro locally and in staging.

Base images, per-image build contexts, and development overlays are defined here and referenced by CI and `infrastructure/`. Secrets and long-lived configuration never live in this folder; they are passed in from the environment at runtime.
