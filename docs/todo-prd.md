# Product Requirements Document — Todo App

**Feature:** Todo App  
**Version:** 1.0  
**Stack:** React + TypeScript · Node.js + Express · PostgreSQL · Jest · Docker

---

## 1. Overview

A full-stack Todo management application that allows authenticated users to create, read, update, and delete todos. Each todo supports tags, due dates, priority levels, and completion status. The system exposes a RESTful API consumed by a React frontend.

---

## 2. Goals

- Provide a fast, reliable CRUD API for todos
- Support per-user data isolation via JWT authentication
- Enable filtering, sorting, and searching todos
- Support tagging and due-date tracking
- Be fully containerized and CI/CD-ready

---

## 3. User Roles

| Role | Description |
|---|---|
| **Guest** | Can register and log in only |
| **Authenticated User** | Can manage their own todos and tags |

---

## 4. Functional Requirements

### 4.1 Authentication

- `POST /auth/register` — Register with `name`, `email`, `password`
  - Password must be ≥ 8 characters, include 1 uppercase, 1 number
  - Returns a JWT access token (expires in 24h) and a refresh token (expires in 7d)
- `POST /auth/login` — Login with `email`, `password`; returns same token pair
- `POST /auth/refresh` — Exchange a valid refresh token for a new access token
- `POST /auth/logout` — Invalidate the current refresh token
- All non-auth endpoints require a valid `Authorization: Bearer <token>` header

### 4.2 Todos

Each todo belongs to exactly one user and has:

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID | auto | Primary key |
| `title` | string | yes | Max 255 chars |
| `description` | string | no | Max 2000 chars, markdown allowed |
| `status` | enum | yes | `pending` \| `in_progress` \| `done` |
| `priority` | enum | yes | `low` \| `medium` \| `high` |
| `due_date` | ISO 8601 date | no | Must be today or in the future on create |
| `tags` | string[] | no | Max 10 tags per todo, each max 30 chars |
| `created_at` | timestamp | auto | |
| `updated_at` | timestamp | auto | |

**Endpoints:**

- `GET /todos` — List all todos for the authenticated user
  - Query params: `status`, `priority`, `tag`, `search` (title/description full-text), `sort_by` (`due_date` \| `created_at` \| `priority`), `order` (`asc` \| `desc`), `page`, `limit` (default 20, max 100)
  - Returns paginated response with `data`, `total`, `page`, `limit`
- `POST /todos` — Create a new todo
- `GET /todos/:id` — Get a single todo by ID (must belong to requesting user)
- `PATCH /todos/:id` — Partial update (any subset of fields)
- `DELETE /todos/:id` — Soft-delete (sets `deleted_at`; excluded from all list queries)
- `PATCH /todos/:id/status` — Shorthand to update status only
- `POST /todos/:id/tags` — Add tags to a todo (merged with existing)
- `DELETE /todos/:id/tags/:tag` — Remove a specific tag from a todo

### 4.3 Tags

- Tags are free-form strings scoped to a user
- `GET /tags` — Return all unique tags the user has ever used, with usage counts
- Tag names are case-insensitive (stored lowercase)

### 4.4 Bulk Operations

- `PATCH /todos/bulk` — Accept an array of `{ id, ...fields }` and apply partial updates; return per-item success/failure
- `DELETE /todos/bulk` — Accept an array of IDs and soft-delete all; return count deleted

---

## 5. Non-Functional Requirements

### 5.1 Performance
- List endpoints must respond in < 200ms for up to 10,000 todos per user
- Use database indexes on `user_id`, `status`, `due_date`, `deleted_at`

### 5.2 Security
- Passwords hashed with bcrypt (cost factor ≥ 12)
- JWTs signed with RS256
- Refresh tokens stored hashed in the database
- Rate limiting: 100 requests/min per IP on auth endpoints; 500 requests/min per user on todo endpoints
- Input sanitization on all string fields to prevent XSS
- CORS restricted to the configured frontend origin

### 5.3 Error Handling
All errors return a consistent JSON shape:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "details": [ { "field": "title", "issue": "required" } ]
  }
}
```

Standard error codes: `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `RATE_LIMITED`, `INTERNAL_ERROR`

### 5.4 Pagination
All list endpoints use cursor-based or offset pagination. Default page size is 20; maximum is 100. Response always includes `total` count.

---

## 6. Frontend Requirements

### 6.1 Pages & Views

| Route | Description |
|---|---|
| `/login` | Login form |
| `/register` | Registration form |
| `/todos` | Main todo list with filters sidebar |
| `/todos/:id` | Todo detail / edit view |

### 6.2 Todo List Page
- Display todos in a card or table layout (user-togglable)
- Filter panel: by status, priority, tag, due date range
- Search bar for full-text search (debounced, 300ms)
- Sort controls: by due date, created date, priority
- Inline status toggle (checkbox click → mark done)
- Bulk select + bulk delete / bulk status change
- Empty state illustration when no todos match filters
- Infinite scroll or pagination controls

### 6.3 Todo Detail / Edit
- Inline editing of all fields
- Tag input with autocomplete from user's existing tags
- Due date picker (date only, no time)
- Priority selector (low / medium / high with color coding)
- Delete button with confirmation dialog

### 6.4 UX Requirements
- All async actions show loading spinners
- All errors show toast notifications
- Optimistic UI updates for status toggles
- Mobile-first responsive layout (breakpoints: 375px, 768px, 1280px)
- Accessible: all interactive elements keyboard-navigable, ARIA labels on icon buttons

---

## 7. Data Model Summary

```
users
  id, name, email, password_hash, created_at, updated_at

refresh_tokens
  id, user_id (FK), token_hash, expires_at, revoked_at

todos
  id, user_id (FK), title, description, status, priority,
  due_date, created_at, updated_at, deleted_at

todo_tags
  todo_id (FK), tag (string), created_at
  PRIMARY KEY (todo_id, tag)
```

---

## 8. Acceptance Criteria

- [ ] A user can register, log in, and receive a JWT
- [ ] An unauthenticated request to any `/todos` endpoint returns `401`
- [ ] A user cannot read, edit, or delete another user's todo (returns `403`)
- [ ] Creating a todo with a past `due_date` returns `400 VALIDATION_ERROR`
- [ ] Filtering by `tag=work` returns only todos tagged "work"
- [ ] Soft-deleted todos do not appear in any list or GET by ID
- [ ] Bulk delete of 50 todos completes in a single request
- [ ] All frontend forms show field-level validation errors inline
- [ ] The todo list renders correctly on a 375px mobile screen
- [ ] Unit test coverage ≥ 85% on all backend service functions
- [ ] The full stack starts with `docker compose up` with no manual steps

---

## 9. Out of Scope (v1.0)

- Sharing todos with other users
- Real-time updates (WebSockets)
- File attachments
- Recurring todos
- Email/push notifications
- OAuth (Google, GitHub) login
