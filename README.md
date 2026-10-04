# Relayn

A multi-tenant customer communication and business-action platform, initially
covering official Meta API WhatsApp communication, a shared team inbox, contacts,
conversations, leads, workflows, Meta attribution, and analytics. The architecture
will support additional channels, public APIs, external systems, and vertical
products such as Rental OS.

**Current status:** repository instructions only. **Stage 0 application
scaffolding has NOT been completed yet.** No application code or infrastructure
has been created.

Intended stack: Python, Django, Django REST Framework, PostgreSQL, Redis, and
Celery for the backend; React, TypeScript, Vite, and Tailwind CSS for the frontend.
The architecture is a modular monolith with REST APIs, organization-based
multi-tenancy, and channel-neutral domains behind provider adapters.

Development proceeds in explicitly scoped stages. Read [AGENTS.md](AGENTS.md)
and [ARCHITECTURE.md](ARCHITECTURE.md) before each implementation task. Add only
the modules and capabilities required by the authorized stage, and report the
checks run and unresolved issues at its conclusion.
