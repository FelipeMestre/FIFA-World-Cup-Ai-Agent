# Python Fastapi backend project
**Cross-domain imports**: always use the explicit module name. Never `from src.auth import *`.

```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
from src.posts.constants import ErrorCode as PostsErrorCode
```

## Async Routes

### Decision rule

| Route does this                        | Use         |
|----------------------------------------|-------------|
| `await`-able non-blocking I/O          | `async def` |
| Blocking I/O (no async client exists)  | `def` (sync, runs in threadpool) |
| Mix of both                            | `async def` + `run_in_threadpool` for the blocking part |
| CPU-bound work (>50 ms compute)        | Offload to a worker process (Celery / RQ / Arq) |

### Do / Don't

```python
# DON'T — blocking call inside async route freezes the entire event loop
@router.get("/bad")
async def bad():
    time.sleep(10)            # blocks every request on this worker
    return {"ok": True}

# DO — sync route lets FastAPI run it in a threadpool
@router.get("/sync-ok")
def sync_ok():
    time.sleep(10)            # blocks one threadpool worker, not the loop
    return {"ok": True}

# DO — async route with awaitable sleep
@router.get("/async-ok")
async def async_ok():
    await asyncio.sleep(10)   # yields control, loop keeps serving requests
    return {"ok": True}

# DO — async route that has to call a sync library
from fastapi.concurrency import run_in_threadpool

@router.get("/wrap")
async def wrap():
    result = await run_in_threadpool(legacy_sync_client.fetch, "id")
    return result
```

### Threadpool caveats
- Default Starlette threadpool size is 40. Saturating it slows every sync route.
- Threads cost more than coroutines. Don't use sync routes "just because."

## Pydantic

### Use built-in validators
```python
from enum import StrEnum
from pydantic import AnyUrl, BaseModel, EmailStr, Field


class MusicBand(StrEnum):
    AEROSMITH = "AEROSMITH"
    QUEEN = "QUEEN"
    ACDC = "AC/DC"


class UserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    email: EmailStr
    age: int = Field(ge=18)                     # required, must be >= 18
    favorite_band: MusicBand | None = None
    website: AnyUrl | None = None
```

> **Don't** write `Field(ge=18, default=None)`. The constraint and the default contradict
> each other. Decide: required (`Field(ge=18)`) or optional (`int | None = Field(default=None, ge=18)`).

### Custom base model — modern serialization

`json_encoders` is deprecated in Pydantic v2. Use `@field_serializer` for per-field rules,
or annotate a custom type with `PlainSerializer`.

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, field_serializer


class CustomModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value
```

### Split BaseSettings by domain

`pydantic-settings` is its own package since Pydantic v2.

```python
# src/auth/config.py
from datetime import timedelta
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", env_file=".env", extra="ignore")

    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP_MINUTES: int = 5
    REFRESH_TOKEN_KEY: str
    REFRESH_TOKEN_EXP: timedelta = timedelta(days=30)
    SECURE_COOKIES: bool = True


auth_settings = AuthConfig()
```

## Dependencies

### Use Annotated, not default-arg `Depends(...)`

`Annotated[T, Depends(...)]` is the idiomatic form since FastAPI 0.95 and avoids
gotchas with default values.

```python
# DO — modern Annotated form
from typing import Annotated
from fastapi import Depends

PostDep = Annotated[dict, Depends(valid_post_id)]

@router.get("/posts/{post_id}")
async def get_post(post: PostDep):
    return post

# Avoid — default-argument form (still works, but legacy)
@router.get("/posts/{post_id}")
async def get_post(post: dict = Depends(valid_post_id)):
    return post
```

### Validate inside dependencies (not just inject)
```python
async def valid_post_id(post_id: UUID4) -> dict:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post
```

### Chain dependencies for reuse
```python
async def valid_owned_post(
    post: Annotated[dict, Depends(valid_post_id)],
    token_data: Annotated[dict, Depends(parse_jwt_data)],
) -> dict:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post
```

### Rules
- Dependencies are **cached per request**. Same `Depends(x)` called 5 times in one request → `x` runs once.
- Prefer `async def` dependencies. Sync deps run in the threadpool — wasted overhead for small CPU-only checks.
- Use **the same path-variable name** across endpoints when you want to share a dependency (e.g. `profile_id` in both `/profiles/{profile_id}` and `/creators/{profile_id}`).

## Authentication — JWT

Use **`auth0-fastapi-api==1.0.0b5`** for this project's Auth0 RS256/JWKS/audience boundary (handles JWKS cache, `aud` `https://openbank.api/com/auth`, `permissions[]`/`scope` via `require_permissions`). Use **`PyJWT`** only for non-Auth0 JWT cases — never `python-jose` (unmaintained). `auth0-fastapi-api` is the blessed SDK for this codebase (blessed over stale `PyJWT` for the security boundary).

```python
# This project — Auth0 boundary (blessed)
from fastapi_plugin.fast_api_client import Auth0FastAPI
from openbankapi.config.dependencies import require_permissions  # permissions[] primary, scope fallback

# Generic JWT (non-Auth0) — PyJWT
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except InvalidTokenError as exc:
        raise InvalidCredentials() from exc
```

## Database — SQLAlchemy 2.0 async

Prefer SQLAlchemy 2.0's async API. `encode/databases` is in maintenance mode — don't pick it for new projects.

```python
# src/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine(str(settings.DATABASE_URL), pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionFactory() as session:
        yield session
```

### Naming conventions
- `lower_case_snake`
- Singular tables: `post`, `user`, `post_like`
- Group with prefix: `payment_account`, `payment_bill`
- `_at` suffix for `datetime`, `_date` suffix for `date`
- Use the same FK column name everywhere it appears (`profile_id`, not `user_id` in some tables and `profile_id` in others)

### Index naming convention
```python
from sqlalchemy import MetaData

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
```

### SQL-first, Pydantic-second
- Do joins, aggregation, and JSON shaping in SQL — Postgres is faster than CPython at this.
- Hydrate the result into Pydantic only for response validation, not for transformation.

## Background work — BackgroundTasks vs Celery

| Use BackgroundTasks when…                | Use Celery / Arq / RQ when…                |
|------------------------------------------|--------------------------------------------|
| Task is < 1 second                       | Task takes seconds to minutes              |
| Failure can be silently dropped          | You need retries, dead-letter, or visibility|
| Task is in-process (send email, log row) | Task is CPU-heavy or needs a separate pool |
| You don't need scheduling                | You need cron, ETA, or rate limiting       |

```python
from fastapi import BackgroundTasks

@router.post("/signup")
async def signup(data: SignupIn, bg: BackgroundTasks):
    user = await service.create_user(data)
    bg.add_task(send_welcome_email, user.email)   # fire-and-forget, in-process
    return user
```

> BackgroundTasks run **after the response is sent, in the same worker process**. If the
> worker dies, the task is lost. There is no retry. Don't use them for anything you'd
> page on.

## Testing

### Async client from day one
```python
import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts", json={"title": "hi"})
    assert resp.status_code == 201
```

> **Don't** use `async_asgi_testclient` — it's unmaintained. The example above (httpx +
> `ASGITransport`) is the supported path.

### Override dependencies in tests
Don't monkeypatch internals. Use FastAPI's built-in `dependency_overrides`.

```python
from src.auth.dependencies import parse_jwt_data
from src.main import app


def fake_user():
    return {"user_id": "00000000-0000-0000-0000-000000000001"}


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[parse_jwt_data] = fake_user
    yield
    app.dependency_overrides.clear()
```

## Migrations (Alembic)

- Migrations must be static and reversible.
- Use the async template: `alembic init -t async migrations`
- Descriptive filenames:
  ```ini
  # alembic.ini
  file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
  ```
  → `2026-04-14_add_post_content_idx.py`

## API documentation

### Hide docs outside selected envs
```python
from fastapi import FastAPI
from src.config import settings

SHOW_DOCS_IN = {"local", "staging"}
app_kwargs = {"title": "My API"}
if settings.ENVIRONMENT not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None    # disables /docs and /redoc

app = FastAPI(**app_kwargs)
```

### Document endpoints fully
```python
from fastapi import APIRouter, status

router = APIRouter()


@router.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    description="Creates an item owned by the authenticated user.",
    tags=["items"],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Validation error"},
        status.HTTP_409_CONFLICT:    {"model": ErrorResponse, "description": "Slug already exists"},
    },
)
async def create_item(payload: ItemCreate) -> ItemResponse: ...
```

## Linting

```shell
ruff check --fix src
ruff format src
```

Add to a pre-commit hook or run in CI. Ruff replaces black + isort + autoflake + most of flake8.

---

## Anti-patterns — common AI-agent mistakes

If you're an agent reviewing a diff, check for these. Each is a real failure mode I've
seen agents introduce.

| Anti-pattern | Why it's wrong | Fix |
|---|---|---|
| `requests.get(...)` inside `async def` | Blocks the event loop. `requests` is sync. | Use `httpx.AsyncClient` or `await run_in_threadpool(requests.get, ...)`. |
| `time.sleep` / `open()` / sync DB driver inside `async def` | Same — blocks the loop. | Use the async equivalent (`asyncio.sleep`, `aiofiles`, async driver). |
| `from jose import jwt` | `python-jose` is unmaintained. | `import jwt` (PyJWT). |
| `from async_asgi_testclient import TestClient` | Unmaintained. | `httpx.AsyncClient` + `ASGITransport`. |
| `model_config = ConfigDict(json_encoders={...})` | Deprecated in Pydantic v2. | `@field_serializer` or `Annotated[T, PlainSerializer(...)]`. |
| `Field(ge=18, default=None)` | Constraint contradicts the default. | Pick required or optional, not both. |
| `def get_user(id: int = Depends(...))` (default-arg form) | Legacy; gotchas with default values. | `user: Annotated[User, Depends(...)]`. |
| Catching `Exception` around a route's body | Hides bugs and turns 500s into silent 200s. | Catch the specific exception class; raise `HTTPException` with a meaningful status. |
| `BackgroundTasks` for anything you'd page on | No retry, dies with the worker. | Use Celery / Arq / RQ. |
| Calling a sync ORM session inside `async def` | Blocks the loop, may deadlock the pool. | Use `AsyncSession`. |
| Returning a Pydantic model and *also* setting `response_model=` to that same class | Model gets constructed twice (validate + serialize). | Either return a `dict`/ORM row and let `response_model` validate, or drop `response_model` and trust the return type. |
| Importing across domains via deep paths (`from src.auth.service.user import ...`) | Tight coupling, hard to refactor. | `from src.auth import service as auth_service`. |
| Reusing one `BaseSettings` for the whole app | Hard to reason about, every domain reads every var. | One `BaseSettings` per domain. |
| Mocking the database in integration tests | Mock/prod divergence eventually fires in prod. | Use a real DB (testcontainers, ephemeral schema) and `dependency_overrides` for auth/external services. |

## Quick reference

| Scenario                             | Solution                                          |
|--------------------------------------|---------------------------------------------------|
| Non-blocking I/O                     | `async def` route with `await`                    |
| Blocking I/O (no async client)       | `def` route (sync, runs in threadpool)            |
| Sync library inside async route      | `await run_in_threadpool(fn, *args)`              |
| CPU-intensive work                   | Celery / Arq / RQ worker process                  |
| Request validation against DB        | Dependency that loads + validates + returns       |
| Reuse validation across routes       | Chain dependencies                                |
| Inject dependency in modern style    | `Annotated[T, Depends(...)]`                      |
| Per-request dep caching              | Default behavior — same `Depends(x)` runs once    |
| Per-domain config                    | One `BaseSettings` subclass per domain            |
| Custom datetime serialization        | `@field_serializer`                               |
| Fire-and-forget short task           | `BackgroundTasks`                                 |
| Reliable / scheduled / heavy task    | Celery / Arq / RQ                                 |
| JWT decode                           | `PyJWT` (`import jwt`)                            |
| Async DB                             | SQLAlchemy 2.0 async (`AsyncSession`)             |
| HTTP test client                     | `httpx.AsyncClient` + `ASGITransport`             |
| Swap dep in tests                    | `app.dependency_overrides[dep] = fake`            |
| Lint + format                        | `ruff check --fix` + `ruff format`                |

## My Architecture for APIs 

### The API layer
The api layer contains logic about handling HTTP requests (or WebSockets or wathever protocol used), and errors facing the user. Not business logic. It appears in the /api folder of the project, and after that, a version folder like /api/v1. 
In the routers or controllers, an important part of the logic is to parse the domain model objects to DTO representations before sending response to the user.

The application layer, the presentation layer, the routers layers, the api layer can have application services, that are pieces of reusable logic among several controllers, but they don't orchestrate use cases, or have business logic, an example is for example a service to read cache, with logic repeatable for each read, or the handling of errors that is reusable.

So de folders of the layer can be
dtos
routers
services

### The Domain Layer
The domain layer is the core of the application, there, the business objects, the actors that represent the business cases are represented in a semantic way. These objects store the state of the application and can have logic of their own, due to the encapsulation principle of object oriented programming. The layer is divided in the model, that are these objects layer. And the services layer. All the layers of the system can import stuff from the domain, but the domain must never import stuff from the api layer, it can import abstractions from the infraestructure layer for example.

An object of the model, of the domain can be a User for example. So the domain/model/User.py file will contain a concrete class that holds the state of the user, the first name, last name, email and birthdate for example. So in the domain service, a UserService with the delete_user, create_user, update_user methods allong with any other posibility use case can be implemented. The idea is that the domain services implement use cases that are based on orchestrating several operations, for example, delete the user from the database and also delete it from an Auth provider, that will require a domain service, cause it is too complex to put that logic into the API layer. But, if it only requires to delte it from a database, the controller can call the database repository (via an interface) directly. 

Another chapter of the domain layer are exceptions, this is a way of capturing errors in an understandable way for the app, so every other layer can import these exceptions types and after that decide how to present it to the user or how to log it in a log system

### The Infraestructure Layer
The purpose of the infraestructure layer is to serve as a fachade for al the external dependencies that the project has. For example, if i use a Postgres Database, the infra/postgres layer must contain all the configuracion, repositories to access data, interfaces so the system doesn't depend on concrete classes and database can be easily changed without changing the presentation API layer or the business logic models or services by no means possible.

Each folder inside infraestructure could have the following structure:
infra/example/config
infra/example/repositories
infra/example/schemas
infra/example/interfaces

Config has a config.py file that handles all the configuration needed to get wathever is running there running
Repositories are services that implement concrete logic about interacting with this component, but, they can also be tied to a certain entity. In the case of a database for example, each entity handled in the database must have an appart repository, for example:
UserRepository
ItemRepository
AccountRepository

Each one of these can have a Update, Create, Upsert, Delete, List method, each with its own parameters, error handling, logic of interacting with the db, chunking of data, aggregating of data, joins, filters, and validations. The services or routers can depend on INTERFACES OF REPOSITORIES, not the concrete classes. A controller method can only depend on one or two repositories interfaces only for simple cases, like a list, that is just passing parameters to a repository and returning back the result. If the operation involves making several operations, the use case must be orchestrated in a domain service that can depend on any number of services or repositories. Each repository file must have an available interface and dependency of itself so the other files can import them, the concrete class must be private

The schemas folder has schema files, that contain model like classes that can have validations, and represent the domain objetcs in this particular component. for example, maybe the database has its own representation of the model in a relational database schema way, that maybe is not the same structure the API has for the model, and the schema holds the version of the classes of the model in a relational database way of representation. And the repositories can bring data and transform from schema classes to domain objects.

The database part of the infra can have also a migrations folder, migrations are ways of changing the schema of the infraestructure component as the app development adds or takes more requirements and use cases.

Any loging service used, can have a folder in the infraestructure layer, with the same filosophy of use, maybe a path to store plain logs or some event folder with event classes to have a more structured approach, but the app should not depend on a concrete log system, it is a component that must be detached from the domain or presentation (controllers or routers) layer in the infraestructure layer.

#### Example of a repository implementation
```python
from abc import ABC, abstractmethod
from fastapi import FastAPI, Depends

# 1. Define the Interface contract
class UserRepositoryInterface(Protocol):
    @abstractmethod
    def get_user_by_id(self, user_id: int) -> dict:
        pass

# 2. Implement a concrete version (e.g., SQL database)
class SQLUserRepository(UserRepositoryInterface):
    def get_user_by_id(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Alice", "source": "SQL Database"}

# 3. Use the interface inside a FastAPI endpoint

def get_user_repo() -> UserRepositoryInterface:
    return SQLUserRepository()  # Can easily change to MongoUserRepository later

@app.get("/users/{user_id}")
def read_user(user_id: int, repo: UserRepositoryInterface = Depends(get_user_repo)):
    return repo.get_user_by_id(user_id)
```

<!-- BEGIN:nextjs-agent-rules -->

# NextJS 16 frontend project 
Next.js 16 is strictly the frontend and all business logic and data access live in a separate backend, I use a feature-oriented architecture with a thin routing layer. The main goal is to make the codebase easy to navigate by business domain, prevent shared folders from becoming dumping grounds, and keep dependencies predictable as the number of features grows.
For example:

```
    src/
    ├── app/
    │   ├── (auth)/
    │   │   ├── login/
    │   │   │   └── page.tsx
    │   │   └── forgot-password/
    │   │       └── page.tsx
    │   │
    │   ├── (dashboard)/
    │   │   ├── layout.tsx
    │   │   ├── dashboard/
    │   │   │   └── page.tsx
    │   │   ├── customers/
    │   │   │   └── page.tsx
    │   │   ├── accounts/
    │   │   │   └── page.tsx
    │   │   ├── transactions/
    │   │   │   └── page.tsx
    │   │   └── reports/
    │   │       └── page.tsx
    │   │
    │   ├── layout.tsx
    │   ├── error.tsx
    │   ├── loading.tsx
    │   └── globals.css
    │
    ├── features/
    │   ├── customers/
    │   │   ├── components/
    │   │   ├── hooks/
    │   │   ├── api/
    │   │   ├── schemas/
    │   │   ├── types.ts
    │   │   └── index.ts
    │   │
    │   ├── accounts/
    │   │   ├── components/
    │   │   ├── hooks/
    │   │   ├── api/
    │   │   ├── schemas/
    │   │   ├── types.ts
    │   │   └── index.ts
    │   │
    │   ├── transactions/
    │   ├── reports/
    │   ├── users/
    │   └── ...
    │
    ├── components/
    │   ├── ui/
    │   ├── layout/
    │   └── shared/
    │
    ├── lib/
    │   ├── api/
    │   ├── auth/
    │   ├── permissions/
    │   ├── formatting/
    │   ├── validation/
    │   └── utils/
    │
    ├── providers/
    ├── config/
    └── types/
```

The philosophy

The most important decision is that app is responsible for routing, not business functionality. A page.tsx should mostly compose a screen from the appropriate feature components. You don't want 500-line pages containing API calls, state management, validation, and business-specific UI logic. Next.js route groups such as (dashboard) are particularly useful here because they let you organize the application without affecting the URL structure.

The features directory is the heart of the application. For a banking system, for example, every significant banking capability gets its own boundary: customers, accounts, transactions, loans, payments, reports, and so on. Everything that primarily belongs to that capability lives together. For example, features/accounts can contain the account table, account details, account filters, hooks, API client functions, validation schemas, and types. This is much more maintainable than having one global components, hooks, and services directory containing hundreds of unrelated files.

The api directory inside a feature should contain frontend API clients, not backend business logic:

```
features/accounts/api/
├── get-accounts.ts
├── get-account.ts
├── create-account.ts
└── update-account.ts
```

These functions know how to communicate with your backend. They should not implement banking rules. The backend remains the source of truth for authorization, business rules, transactions, calculations, and persistence.

For example:

```
features/accounts/components/account-table.tsx
        ↓
features/accounts/api/get-accounts.ts
        ↓
Backend API
        ↓
Database
```

The global components directory should stay small. ui contains genuinely generic components such as buttons, dialogs, inputs, tables, dropdowns, and similar primitives. layout contains application-wide structural components such as the sidebar and header. shared contains reusable components that don't belong to a particular domain, such as an empty state or confirmation dialog.

A useful rule is:

If something belongs to one feature, keep it inside that feature. If it is genuinely reusable across features, promote it to components.

Don't prematurely put everything into shared folders.

Similarly, lib is for application infrastructure, not business features. Your HTTP client, authentication integration, permission helpers, date/number formatting, and common utilities belong there. For example:

```
lib/api/client.ts
lib/auth/session.ts
lib/permissions/can.ts
lib/formatting/currency.ts
```

I would also keep dependencies flowing in one direction:

```
app
 ↓
features
 ↓
lib
```

A customer component can use the customer API and shared UI. The customer feature can use lib/api. But lib should never import something from features/customers. This prevents circular dependencies and keeps the architecture understandable.

Finally, I'd treat each feature as a potential bounded boundary. If accounts eventually becomes enormous, you can internally split it further without changing the rest of the application:

```
features/accounts/
├── account-list/
├── account-details/
├── account-creation/
├── account-transactions/
├── api/
└── types.ts
```

This gives you an architecture that can start relatively simple but evolve with the product.

The key principle I'd follow throughout the project is locality: when an engineer is asked to modify "customer onboarding," they should be able to go to features/customers and find almost everything relevant there. In a banking system with dozens or hundreds of features, that property is far more valuable than having a theoretically perfect folder hierarchy.

# This is NOT the Next.js you know
 
This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `/frontend/node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.
 
This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.
 

## For tests
tests/
├── unit/
│   ├── features/
│   │   ├── customers/
│   │   ├── accounts/
│   │   └── transactions/
│   └── lib/
│
├── integration/
│   ├── customers/
│   ├── accounts/
│   └── transactions/
│
└── e2e/
    ├── authentication/
    ├── customers/
    ├── accounts/
    └── transactions/

The distinction I'd make is:

unit/

Tests an isolated piece of frontend behavior.

For example:

tests/unit/features/accounts/
├── account-table.test.tsx
├── account-filters.test.tsx
└── account-validation.test.ts

These should be fast and shouldn't require the real backend.

integration/

Tests how multiple frontend pieces work together.

For example:

tests/integration/accounts/
└── account-list.test.tsx

You might render the account page, mock the backend API, interact with filters, pagination, loading states, errors, etc.

The important point is that you don't test the backend through these tests. The backend should have its own integration and unit test suite in its own project.

## Tailwind

Prefer Tailwind utility classes over hand-written CSS whenever a utility already does the job. The component layer is shadcn/ui (`components/ui/*` — `Button`, `Input`, `Label`, `Select`, `Dialog`, `Card`, `Table`, `Badge`, `Tabs`, `Alert`), styled via CSS variables in `app/globals.css` bridged onto this project's own brand tokens (`--color-accent`, `--spacing-ds-*`, `--radius-*`, etc.) rather than shadcn's own default palette — the look is this app's own, the components underneath are shadcn's. Reach for a hand-written `@layer components` class only for a visual pattern reused across multiple components with no shadcn equivalent — `.field` (a Label+Input(+error) wrapper) is the one surviving example — never as the first resort for a one-off tweak, and never as a substitute for an existing shadcn component.

### Do / Don't

```tsx
// DON'T — a new CSS file/class for a one-off layout tweak
// some.module.css
.wrapper { display: flex; gap: 12px; margin-top: 16px; }

// DO — Tailwind utilities, using this project's own ds-* spacing scale
<div className="flex gap-ds-3 mt-ds-4">

// DON'T — inline styles for anything Tailwind already expresses
<div style={{ display: "flex", alignItems: "center" }}>

// DO
<div className="flex items-center">
```

### Rules

- Use Tailwind utilities for layout, spacing, typography, and one-off visual adjustments — don't reach for a new CSS class or file before checking whether a utility already covers it.
- Use this project's own `--spacing-ds-*` scale (`gap-ds-2`, `p-ds-4`, `mt-ds-6`, ...) instead of Tailwind's default numeric scale, per `app/globals.css`'s own convention. Don't mix both scales in the same component.
- Check for an existing shadcn component (`components/ui/*`) before reaching for a new one — the same is true for a `@layer components` class, kept only for a pattern with no shadcn equivalent (`.field`, the Label+Input(+error) wrapper, is the one that survived) and only once genuinely reused across 2+ components, not preemptively for a single usage.
- Never use inline `style={{...}}` when the same result is expressible in Tailwind utilities.
- Never hardcode a color, spacing, or radius value that already has a design-system token (`--color-accent-700`, `--spacing-ds-3`, `--radius-md`, ...) — reference the token instead of duplicating its value.
- A new standalone CSS file (`*.module.css` or similar) is a last resort. If you add one, justify why Tailwind utilities and the existing `@layer components` classes weren't enough — the same discipline this doc already asks for inline imports.
<!-- END:nextjs-agent-rules -->


# CODE QUALITY STANDARDS
- A file must not go above 400 lines, in case facing this situation, the classes or the class of the file must be splitted in to different files with their or responsibility, and if needed, they must interact with themselves to get the business case right.
- **Clean Code Principles**: Evaluate adherence to clean code tenets including single responsibility, meaningful names, small functions, and clear intent
- **Import Organization**: Prefer top-level imports and flag inline imports unless they are for heavy dependencies with clear performance justification and documentation
- **Naming Excellence**: Scrutinize variable, function, class, and module names for clarity, precision, and intent revelation - names should match actual behavior and distinguish between observed vs. theoretical data
- **Fail-Fast Philosophy**: Assess defensive programming practices, assertion usage, input validation, and early error detection - prefer stopping execution over silently handling errors
- **Type Safety Over Strings**: Flag "stringly typed" code where enums, Literal types, or constants would catch errors at compile/type-check time rather than runtime (e.g., `phase: Literal["pre_cycle", "post_cycle"]` instead of `phase: str`)
- **DRY Violations**: Identify and suggest solutions for code duplication, repeated logic patterns, and opportunities for abstraction
- **Architectural Clarity**: Assess whether classes handle single responsibilities or inappropriately mix multiple concerns
- Functions should do one thing well and have clear, descriptive names that match their actual behavior
- Variables should reveal intent without requiring comments - names should clearly indicate what they represent
- Code should fail fast with meaningful error messages and appropriate assertions - better to stop than silently proceed with bad data
- Classes should have single responsibilities rather than mixing multiple concerns or data formats
- Complex systems need central documentation with examples and clear architectural explanations
- Duplication should be eliminated through proper abstraction
- Code should be self-documenting with strategic module-level documentation for complex systems


**TEST QUALITY ANTIPATTERNS:**

Flag these testing smells with high priority:

- **Mock Abuse**: Creating fake implementations instead of using real data/fixtures. Flag any `Mock()` or `@patch` usage — mocking should be a last resort, not a default
- **Trivial Mocks**: Mocking return values instead of testing real behavior (e.g., `mock_model.predict.return_value = [1, 2, 3]`)
- **Fake Test Data**: Using `{"dummy": "values"}` instead of real fixtures. Check for `conftest.py` or test fixtures that should be used instead
- **Unjustified Test Skips**: Any `@pytest.mark.skip`, `@unittest.skip`, or `pytest.skip()` without clear justification. Skipped tests often indicate incomplete functionality that should be addressed, not deferred
- **Missing Integration Tests**: Tests that never exercise real system components, only mocked versions


## CODE SMELL CATEGORIES
Take into account this cases, these are examples of bad quality code
### 1. Logic Structure Hints
**Deep Nesting (>3 levels)**
```python
# DETECT: Logic that could be expressed as higher-level concepts
def process_sequences(sequences):
    for seq in sequences:
        if seq.is_valid():
            if seq.length > MIN_LENGTH:
                if seq.has_required_features():
                    # deeply nested logic here
```
*Suggestion: "Consider expressing this logic in terms of higher-level concepts (helper functions)"*

**Complex Conditionals**
```python
# DETECT: Multi-condition logic that obscures intent
if (model.is_trained() and data.is_validated() and
    config.get("use_cache", False) and not force_retrain):
    # complex condition logic
```
*Suggestion: "This condition might be clearer as a named predicate method"*

### 2. Method Design Smells
**Flags Extending Behavior**
```python
# DETECT: String/enum flags that determine core behavior or data handling
def process_data(sequences, data_type="protein"):
    if data_type == "protein":
        return process_protein_sequences(sequences)
    elif data_type == "dna":
        return process_dna_sequences(sequences)
    # core behavior determined by string flag

def run_analysis(data, analysis_mode="standard"):
    if analysis_mode == "phylogenetic":
        # completely different algorithm
    elif analysis_mode == "comparative":
        # different algorithm again
```
*Suggestion: "Consider separate methods or classes when flags determine fundamentally different behaviors or data handling"*

**Methods Doing Multiple Operations**
```python
# DETECT: Method names with "and" suggesting multiple responsibilities
def load_and_validate_and_process_data(file_path):
    # loading, validation, and processing all in one method
```
*Suggestion: "Methods with 'and' in their names often handle multiple concerns"*

**Long Parameter Lists (>5 parameters)**
```python
# DETECT: Many parameters suggesting grouping opportunities
def train_model(data, epochs, learning_rate, batch_size, optimizer, scheduler, callbacks):
    # many related parameters
```
*Suggestion: "Consider grouping related parameters into configuration objects"*

### 3. Clarity and Intent Issues
**Comments Explaining Confusing Code**
```python
# DETECT: Comments that explain what code is doing rather than why
# Convert to one-hot encoding and reshape for the model
encoded = np.eye(vocab_size)[token_ids].reshape(-1, vocab_size * seq_len)
```
*Suggestion: "This logic might benefit from clearer naming or extraction to a well-named helper function"*

**Magic Numbers in Domain Logic**
```python
# DETECT: Unexplained numeric constants
if accuracy > 0.95:  # Why 0.95?
    return "excellent"
elif accuracy > 0.8:  # Why 0.8?
    return "good"
```
*Suggestion: "Consider extracting these thresholds as named constants to clarify their significance"*

**Primitive Obsession**
```python
# DETECT: Using primitives where domain objects would clarify
def analyze_sequence(sequence_string, sequence_type, sequence_id, sequence_metadata):
    # multiple primitives that could be a Sequence object
```
*Suggestion: "These related primitives might benefit from being grouped into a domain object"*

### 4. Type and Interface Hints
**Complex Return Types**
```python
# DETECT: Functions returning multiple unrelated types
def get_model_info(model_path) -> Union[Dict[str, Any], List[str], None]:
    # returning different types based on conditions
```
*Suggestion: "Multiple return types may indicate this function has multiple responsibilities"*

**Data Clumps**
```python
# DETECT: Same group of parameters appearing together repeatedly
def method_a(file_path, format_type, encoding):
    pass

def method_b(file_path, format_type, encoding):
    pass

def method_c(file_path, format_type, encoding):
    pass
```
*Suggestion: "These parameters often appear together; consider grouping them into a FileSpec object"*

### 5. Maintainability Signals
**Inconsistent Naming Patterns**
```python
# DETECT: Similar concepts using different styles
def get_sequences():     # verb_noun
    pass

def sequence_count():    # noun_verb
    pass

def numProteins():       # differentCase
    pass
```
*Suggestion: "Similar concepts use different naming styles; consistency aids comprehension"*

**Feature Envy**
```python
# DETECT: Methods obsessed with another object's data
def calculate_stats(self, sequence):
    length = sequence.get_length()
    composition = sequence.get_composition()
    gc_content = sequence.get_gc_content()
    # method mostly uses sequence's data
    return length * composition + gc_content
```

# Gitflow

# Gitflow Workflow Rules

## Main Branches

### main (or master)
- Contains production-ready code
- Never commit directly to main
- Only accepts merges from:
  - hotfix/* branches
  - release/* branches
- Must be tagged with version number after each merge

### develop
- Main development branch
- Contains latest delivered development changes
- Source branch for feature branches
- Never commit directly to develop

## Supporting Branches

### feature/*
- Branch from: develop
- Merge back into: develop
- Naming convention: feature/[issue-id]-descriptive-name
- Example: feature/123-user-authentication
- Must be up-to-date with develop before creating PR
- Delete after merge

### release/*
- Branch from: develop
- Merge back into: 
  - main
  - develop
- Naming convention: release/vX.Y.Z
- Example: release/v1.2.0
- Only bug fixes, documentation, and release-oriented tasks
- No new features
- Delete after merge

### hotfix/*
- Branch from: main
- Merge back into:
  - main
  - develop
- Naming convention: hotfix/vX.Y.Z
- Example: hotfix/v1.2.1
- Only for urgent production fixes
- Delete after merge

## Commit Messages

- Format: `type(scope): description`
- Types:
  - feat: New feature
  - fix: Bug fix
  - docs: Documentation changes
  - style: Formatting, missing semicolons, etc.
  - refactor: Code refactoring
  - test: Adding tests
  - chore: Maintenance tasks

## Version Control

### Semantic Versioning
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality
- PATCH version for backwards-compatible bug fixes

## Pull Request Rules

1. All changes must go through Pull Requests
2. Required approvals: minimum 1
3. CI checks must pass
4. No direct commits to protected branches (main, develop)
5. Branch must be up to date before merging
6. Delete branch after merge

## Branch Protection Rules

### main & develop
- Require pull request reviews
- Require status checks to pass
- Require branches to be up to date
- Include administrators in restrictions
- No force pushes
- No deletions

## Release Process

1. Create release branch from develop
2. Bump version numbers
3. Fix any release-specific issues
4. Create PR to main
5. After merge to main:
   - Tag release
   - Merge back to develop
   - Delete release branch

## Hotfix Process

1. Create hotfix branch from main
2. Fix the issue
3. Bump patch version
4. Create PR to main
5. After merge to main:
   - Tag release
   - Merge back to develop
   - Delete hotfix branch
