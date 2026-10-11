# API Reference

Base URL: `http://localhost:8000`
Interactive docs: `/docs` (Swagger) and `/redoc`.

All `/documents` and `/chat` endpoints require a Bearer token:
`Authorization: Bearer <token>`.

---

## Auth

### `POST /auth/register`
Create a new account.

Request:
```json
{ "email": "user@example.com", "password": "secret1" }
```
Response `201`:
```json
{ "id": 1, "email": "user@example.com" }
```

### `POST /auth/login`
Form-encoded (OAuth2 password flow). `username` is the email.

```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=user@example.com&password=secret1"
```
Response `200`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

---

## Documents

### `POST /documents` (multipart)
Upload and ingest a UTF-8 text/markdown file.

```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer <jwt>" \
  -F "file=@notes.txt" -F "namespace=default"
```
Response `201`:
```json
{ "id": 1, "namespace": "default", "filename": "notes.txt", "chunk_count": 12 }
```

### `GET /documents?namespace=default`
List documents in a namespace.

### `DELETE /documents/{id}`
Delete a document and its chunks. Response `204`.

---

## Chat

### `POST /chat`
Ask a question. Omit `session_id` to start a new conversation.

Request:
```json
{ "question": "What is in my docs?", "namespace": "default", "session_id": null }
```
Response `200`:
```json
{
  "session_id": 1,
  "answer": "...",
  "citations": [
    { "document_id": 1, "filename": "notes.txt", "chunk_index": 0, "snippet": "..." }
  ]
}
```

### `POST /chat/stream`
Same request body; returns a Server-Sent Events stream. Each event is
`data: <token>`, ending with `data: [DONE]`.

### `GET /chat/sessions/{id}`
Return the full message history for a conversation.

---

## Monitoring

### `GET /health`
```json
{ "status": "ok", "database": true }
```

### `GET /metrics`
```json
{ "users": 1, "documents": 3, "chunks": 40, "chat_sessions": 2 }
```
