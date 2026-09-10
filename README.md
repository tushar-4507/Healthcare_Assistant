# Healthcare Assistant

A React + FastAPI + MongoDB + RAG healthcare chatbot.

## Architecture

```text
React Frontend
   |
   | HttpOnly JWT cookie + REST APIs
   v
FastAPI
   |---- MongoDB -> users / conversations / messages
   |
   |---- FAISS -> medical knowledge retrieval
   |
   `---- Groq LLM -> final response
```

## New upgrades

- MongoDB-backed user accounts.
- Password hashing; raw passwords are never stored.
- JWT authentication stored in an HttpOnly cookie.
- Protected chat routes.
- Per-user chat conversations.
- Persistent chat history in MongoDB.
- ChatGPT-style left sidebar with New Chat, conversation selection and delete.
- Recent conversation messages are included as model context for follow-up questions.
- Conversation title is generated from the first message.
- RAG embedding model is consistent between index creation and API loading.

See `Backend/README.md` for setup.
