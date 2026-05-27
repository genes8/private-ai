---
trigger: always_on
---
---
# Communication Rules

1. Speak to me in Serbian.
2. Code always in English.
3. Use python3 instead of python, use pip3 instead of pip.
4. When creating a new app, use FastAPI for the backend and React Tanstack Start with Typescript for the frontend, unless otherwise specified.
5. When creating a new app, use git for version control, unless otherwise specified.
6. Always use postgresql for the database, unless otherwise specified.
7. Always use alembic for database migrations, unless otherwise specified.
8. Always use redis for caching, unless otherwise specified.
9. Always first read every document md file in project structure to get context before starting to code.
10. Always when finish each task, summarize what was done in changelog.md file.
11. Always test app before commit.


# Development Environment Setup

For local development:
- Run PostgreSQL, Redis, and other infrastructure services directly on the local machine (native installation)
- Run application code (FastAPI backend, React-router frontend) natively with hot reload for faster development cycle
- Use virtual environments (venv for Python, node_modules for Node.js) for dependency management
- Use Alembic migrations applied to local PostgreSQL database

For production deployment: 
- Create separate Dockerfiles for backend (FastAPI) and frontend (React-router)
- Use official Docker images for infrastructure (postgres:15-alpine, redis:7-alpine, nginx:alpine)
- Define all services in docker-compose.yml
- Deploy with single command: `docker-compose up -d`
- Never create Dockerfile for standard services like PostgreSQL, Redis, nginx - always use official images

Docker is for deployment, not for daily development work.

# DATABASE RULES — NEVER VIOLATE

## Migrations
- NEVER run `alembic downgrade` without explicit user confirmation
- NEVER auto-generate AND auto-apply migrations in same step
- ALWAYS generate migration first, show it to user, wait for approval before `upgrade head`
- NEVER drop columns or tables unless user explicitly says "drop X"
- NEVER modify existing enum values — only ADD new values via `ALTER TYPE x ADD VALUE 'y'`
- ALWAYS check if migration contains drop_column, drop_table, drop_constraint before applying
- NEVER run `alembic stamp` without explaining what it does
- NEVER DELETE or change user and admins passwords in DATABASE before asking!

## Data Safety
- NEVER run DELETE, TRUNCATE, or DROP on dev database
- NEVER modify seed data without asking
- ALWAYS use `IF NOT EXISTS` / `ON CONFLICT DO NOTHING` in seed scripts
- NEVER reset auth tables (users, sessions, tokens) during feature development

## Enum Changes
- NEVER let alembic autogenerate handle enum changes — always write manually
- ALWAYS use: `op.execute("ALTER TYPE enumname ADD VALUE 'new_val'")`
- NEVER use: `op.drop_column` + recreate for enum changes

## Workflow Order
1. Write/modify SQLAlchemy model
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. SHOW migration file to user and wait for approval
4. Only then: `alembic upgrade head`
5. Run seed script if needed

## Environment
- Dev database: never touch schema without migration
- Test database: can reset freely
- NEVER run pytest fixtures against dev DATABASE_URL
- Always check .env to confirm which DB is active before any operation

## Forbidden Commands (require explicit user confirmation)
- alembic downgrade
- alembic downgrade base
- DROP TABLE
- TRUNCATE
- DELETE FROM users
- alembic stamp
```

---

## Docker izolacija — pravo rešenje

```
docker-compose.yml          # dev okruženje
docker-compose.test.yml     # test okruženje (odvojena baza)
