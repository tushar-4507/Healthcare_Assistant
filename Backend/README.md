# Healthcare Assistant Backend

## 1. Create the environment

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```powershell
.venv\Scripts\activate
```

## 2. Configure environment variables

Copy `.env.example` to `.env` and set:

```env
GROQ_API_KEY=...
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=healthcare_assistant
JWT_SECRET=...
```

You can use MongoDB Atlas instead of a local MongoDB server.

## 3. Build the FAISS index

The API and index builder must use the same embedding model. This project uses:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Run:

```bash
python creatememoryllm.py
```

## 4. Start the API

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

or:

```bash
./start.sh
```

## Authentication

Authentication is now:

```text
React -> FastAPI -> MongoDB
                 |
                 -> password hash
                 -> JWT in HttpOnly cookie
```

The browser sends the cookie automatically with `credentials: "include"`.

## Chat memory

MongoDB stores:

- `users`
- `conversations`
- `messages`

A conversation belongs to exactly one user. The chat endpoint saves the user message and assistant response, and the latest messages are reused as history when generating a follow-up answer.
