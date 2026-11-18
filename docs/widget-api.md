# Rocco API for the website chat widget

Base URL: the Cloud Run service URL (to be published). The site's domain must be listed in
`ALLOWED_ORIGINS`, otherwise the browser blocks the calls (CORS).

Origins to allow in production:

```
ALLOWED_ORIGINS=https://www.casavaiano.it,https://casavaiano.it,https://casavaiano-anteprima.netlify.app,http://127.0.0.1:5280
```

The last one is the site's local preview; drop it if you prefer a stricter production config.

## POST /chat

Request:

```json
{
  "message": "Accettate cani?",
  "session_id": "uuid generated once per browser tab",
  "contact": { "name": "Anna", "email": "anna@example.com", "phone": "+39 333 0000000" }
}
```

- `message`: 1 to 4000 characters.
- `session_id`: optional but recommended; it links the owner's emails to one conversation.
- `contact`: optional; every field optional. Send it if the guest has already filled it in.

Response in production (`EXPOSE_INTERNALS=false`):

```json
{
  "status": "answered",
  "reply": "Sì, i cani sono benvenuti ... Rocco, l'assistente virtuale di CasaVaiano",
  "language": "it",
  "needs_contact": false
}
```

- `status`: `answered` or `escalated`. When `escalated`, the reply is a fixed message saying
  the request was passed to the owner, who will reply personally.
- `needs_contact`: `true` when the request was escalated and the guest has not given an email
  or phone. Show a small form (name, email, phone, optional note) and send it to `/contact`.
- Errors: `422` invalid input, `503` assistant not configured, `500` unexpected error (show
  "Something went wrong, please try again").
- Replies can take 3 to 15 seconds: show a typing indicator.
- Replies are plain text with line breaks; they may contain `**bold**`.

## POST /contact

```json
{
  "session_id": "same uuid as /chat",
  "contact": { "name": "Anna", "email": "anna@example.com" },
  "note": "Preferisco essere chiamata la sera"
}
```

Needs an email or a phone (`422` otherwise). Returns `{"received": true, "owner_notified": true}`.
The owner receives an email linked to the same conversation, with Reply-To set to the guest.

## GET /health

`{"status": "ok", "assistant_name": "Rocco", ...}`: use the name for the widget title.

## Widget notes

- The assistant must be presented as a virtual assistant (Rocco, named after the farm's cat).
- Link the privacy notice: messages are processed by Anthropic (LLM) and Langfuse (tracing).
- Each message is answered on its own for now; conversation history is not used yet.
