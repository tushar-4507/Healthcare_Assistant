# ============================================================
# Healthcare Assistant API
# MongoDB + JWT + FAISS + Groq + Conversation Memory
#
# macOS Apple-Silicon stability/performance adjustments:
# - Limit native math/OpenMP threads.
# - Disable tokenizer parallelism.
# - Allow duplicate OpenMP runtimes as a LOCAL WORKAROUND.
# - Serialize FAISS/RAG execution with a lock.
# - Run blocking RAG work in a threadpool so FastAPI remains
#   responsive while the model is generating.
#
# IMPORTANT:
# The KMP_DUPLICATE_LIB_OK workaround is not a permanent fix.
# A single OpenMP runtime is the proper long-term solution.
# ============================================================

import os

# ------------------------------------------------------------
# MUST be set BEFORE importing torch / sentence-transformers /
# FAISS-related modules.
# ------------------------------------------------------------

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# LOCAL MAC WORKAROUND:
# PyTorch and pip-installed FAISS can load different copies of
# libomp on macOS. Without this, the process may abort with:
# "OMP: Error #15 ... multiple copies of the OpenMP runtime".
#
# This is an unsafe workaround according to the OpenMP runtime
# warning. Use only for this local development environment.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


import re
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
import faiss
from bson import ObjectId
from dotenv import load_dotenv, find_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    Response,
    Cookie,
    Depends,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field

from pymongo import (
    ASCENDING,
    DESCENDING,
    MongoClient,
    ReturnDocument,
)

from pwdlib import PasswordHash

from langchain_groq import ChatGroq
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate


# ============================================================
# FAISS THREAD CONTROL
# ============================================================

faiss.omp_set_num_threads(1)

# Only one RAG/FAISS operation at a time.
# This is deliberately conservative for an 8 GB Apple Silicon Mac.
RAG_LOCK = threading.Lock()


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(find_dotenv())

app = FastAPI(
    title="Healthcare Assistant API",
    version="2.2.0",
)


# ============================================================
# CORS
# ============================================================

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

FRONTEND_ORIGINS = list(
    dict.fromkeys(
        [
            FRONTEND_URL,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MONGODB
# ============================================================

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv(
    "MONGODB_DB_NAME",
    "healthcare_assistant",
)

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is not configured in Backend/.env"
    )

mongo_client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=5000,
)

mongo_db = mongo_client[MONGODB_DB_NAME]

users_collection = mongo_db["users"]
conversations_collection = mongo_db["conversations"]
messages_collection = mongo_db["messages"]


# ============================================================
# MONGODB INDEXES
# ============================================================

users_collection.create_index(
    [("mobile", ASCENDING)],
    unique=True,
)

conversations_collection.create_index(
    [
        ("user_id", ASCENDING),
        ("updated_at", DESCENDING),
    ]
)

messages_collection.create_index(
    [
        ("conversation_id", ASCENDING),
        ("created_at", ASCENDING),
    ]
)


# ============================================================
# JWT + PASSWORD HASHING
# ============================================================

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is not configured in Backend/.env"
    )

JWT_ALGORITHM = "HS256"

JWT_EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", "60")
)

AUTH_COOKIE_NAME = "healthchat_token"

password_hash = PasswordHash.recommended()


# ============================================================
# JWT FUNCTIONS
# ============================================================

def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(
            minutes=JWT_EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def set_auth_cookie(
    response: Response,
    token: str,
) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,       # Local HTTP development
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def get_current_user(
    token: Optional[str] = Cookie(
        default=None,
        alias=AUTH_COOKIE_NAME,
    )
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        try:
            object_id = ObjectId(user_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID",
            )

        user = users_collection.find_one(
            {"_id": object_id}
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class SignupRequest(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=80,
    )
    mobile: str = Field(
        pattern=r"^\d{10}$"
    )
    password: str = Field(
        min_length=6,
        max_length=128,
    )


class LoginRequest(BaseModel):
    mobile: str = Field(
        pattern=r"^\d{10}$"
    )
    password: str = Field(
        min_length=1,
        max_length=128,
    )


class ChatQuery(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=4000,
    )
    conversation_id: Optional[str] = None


class ConversationCreate(BaseModel):
    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=100,
    )


# ============================================================
# FAISS / EMBEDDINGS
# ============================================================

DB_FAISS_PATH = "vectorstore/db_faiss"

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

db = FAISS.load_local(
    DB_FAISS_PATH,
    embedding_model,
    allow_dangerous_deserialization=True,
)

retriever = db.as_retriever(
    search_kwargs={"k": 2},
)


# ============================================================
# RAG PROMPT
# ============================================================

CUSTOM_PROMPT_TEMPLATE = """
You are a healthcare assistant chatbot.

Use the retrieved medical context as the primary source of
information. Use the recent conversation history only to
understand follow-up questions.

Important rules:
1. Do not invent medical facts.
2. Do not provide a definitive diagnosis.
3. Keep answers concise and easy to understand.
4. For serious or urgent symptoms, advise the user to contact
   a qualified medical professional.
5. Do not claim a treatment is guaranteed to work.

When appropriate, use this structure:

Overview:
Short and simple explanation.

Common Symptoms:
Bullet points.

Treatment Options:
Bullet points when relevant.

Causes / Prevention Tips:
Bullet points when relevant.

Key Points:
Bullet points when relevant.

Advice:
One simple health recommendation.

Retrieved Medical Context:
{context}

Conversation History and Current User Question:
{question}

Answer:
"""


def set_custom_prompt(
    template: str,
) -> PromptTemplate:
    return PromptTemplate(
        template=template,
        input_variables=[
            "context",
            "question",
        ],
    )


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not configured in Backend/.env"
    )

# Can be changed from Backend/.env:
# GROQ_MODEL=openai/gpt-oss-20b
GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

llm = ChatGroq(
    model_name=GROQ_MODEL,
    temperature=0.1,
    groq_api_key=GROQ_API_KEY,
    timeout=30,
    max_retries=1,
)


# ============================================================
# RETRIEVAL QA CHAIN
# ============================================================

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=False,
    chain_type_kwargs={
        "prompt": set_custom_prompt(
            CUSTOM_PROMPT_TEMPLATE
        )
    },
)


# ============================================================
# RESPONSE FORMATTER
# ============================================================

def format_response(text: str) -> str:
    if not text:
        return ""

    text = (
        text
        .replace("**", "")
        .replace("###", "")
        .strip()
    )

    sections = {
        "Overview:": "🩺 Overview:",
        "Common Symptoms:": "• Common Symptoms:",
        "Symptoms:": "• Symptoms:",
        "Treatment Options:": "💊 Treatment Options:",
        "Causes / Prevention Tips:": "⚠️ Causes / Prevention Tips:",
        "Causes / Prevention:": "⚠️ Causes / Prevention:",
        "Key Points:": "📘 Key Points:",
        "Advice:": "✅ Advice:",
    }

    for key, value in sections.items():
        text = re.sub(
            rf"\b{re.escape(key)}",
            f"\n{value}",
            text,
        )

    text = re.sub(
        r"^\s*[-*]\s+",
        "• ",
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# SERIALIZATION
# ============================================================

def serialize_user(user):
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "mobile": user["mobile"],
    }


def serialize_conversation(doc):
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "created_at": doc["created_at"].isoformat(),
        "updated_at": doc["updated_at"].isoformat(),
    }


def serialize_message(doc):
    return {
        "id": str(doc["_id"]),
        "role": doc["role"],
        "content": doc["content"],
        "created_at": doc["created_at"].isoformat(),
    }


# ============================================================
# CONVERSATION HELPERS
# ============================================================

def conversation_owned_by_user(
    conversation_id: str,
    user_id: ObjectId,
):
    try:
        object_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation id",
        )

    conversation = conversations_collection.find_one(
        {
            "_id": object_id,
            "user_id": user_id,
        }
    )

    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation


def build_history(
    conversation_id: ObjectId,
    limit: int = 12,
) -> str:
    docs = list(
        messages_collection.find(
            {"conversation_id": conversation_id}
        )
        .sort(
            "created_at",
            DESCENDING,
        )
        .limit(limit)
    )

    docs.reverse()

    if not docs:
        return "No previous messages."

    history_lines = []

    for item in docs:
        role = (
            "User"
            if item["role"] == "user"
            else "Assistant"
        )

        history_lines.append(
            f"{role}: {item['content']}"
        )

    return "\n".join(history_lines)


# ============================================================
# RAG EXECUTION
# ============================================================

def run_rag(question: str) -> str:
    """
    Synchronous/blocking RAG operation.

    It runs in a threadpool from the FastAPI endpoint so the
    event loop remains responsive to other frontend requests.
    """

    with RAG_LOCK:
        response_data = qa_chain.invoke(
            {
                "query": question
            }
        )

    raw_result = (
        response_data.get("result", "")
        .strip()
    )

    formatted_result = format_response(
        raw_result
    )

    if (
        not formatted_result
        or len(formatted_result) < 20
    ):
        return (
            "❌ Sorry, I don't have enough "
            "information to answer that."
        )

    return formatted_result


# ============================================================
# AUTH APIs
# ============================================================

@app.post("/auth/signup")
async def signup(
    payload: SignupRequest,
    response: Response,
):
    existing_user = users_collection.find_one(
        {"mobile": payload.mobile}
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Mobile number is already registered",
        )

    now = datetime.now(timezone.utc)

    user_doc = {
        "name": payload.name.strip(),
        "mobile": payload.mobile,
        "password_hash": password_hash.hash(
            payload.password
        ),
        "created_at": now,
    }

    try:
        result = users_collection.insert_one(
            user_doc
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(
                status_code=409,
                detail="Mobile number is already registered",
            )
        raise

    token = create_access_token(
        str(result.inserted_id)
    )

    set_auth_cookie(
        response,
        token,
    )

    created_user = {
        **user_doc,
        "_id": result.inserted_id,
    }

    return {
        "user": serialize_user(created_user)
    }


@app.post("/auth/login")
async def login(
    payload: LoginRequest,
    response: Response,
):
    user = users_collection.find_one(
        {"mobile": payload.mobile}
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid mobile number or password",
        )

    if not password_hash.verify(
        payload.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid mobile number or password",
        )

    token = create_access_token(
        str(user["_id"])
    )

    set_auth_cookie(
        response,
        token,
    )

    return {
        "user": serialize_user(user)
    }


@app.get("/auth/me")
async def me(
    user=Depends(get_current_user),
):
    return {
        "user": serialize_user(user)
    }


@app.post("/auth/logout")
async def logout(
    response: Response,
):
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
    )

    return {
        "message": "Logged out successfully"
    }


# ============================================================
# DEBUG COOKIE API
# ============================================================

@app.get("/debug/cookie")
async def debug_cookie(
    token: Optional[str] = Cookie(
        default=None,
        alias=AUTH_COOKIE_NAME,
    ),
):
    return {
        "cookie_name": AUTH_COOKIE_NAME,
        "cookie_received": token is not None,
        "token_length": len(token) if token else 0,
    }


# ============================================================
# CONVERSATION APIs
# ============================================================

@app.get("/conversations")
async def list_conversations(
    user=Depends(get_current_user),
):
    conversations = conversations_collection.find(
        {"user_id": user["_id"]}
    ).sort(
        "updated_at",
        DESCENDING,
    )

    return {
        "conversations": [
            serialize_conversation(doc)
            for doc in conversations
        ]
    }


@app.post("/conversations")
async def create_conversation(
    payload: ConversationCreate,
    user=Depends(get_current_user),
):
    now = datetime.now(timezone.utc)

    title = (
        payload.title.strip()
        or "New Chat"
    )

    result = conversations_collection.insert_one(
        {
            "user_id": user["_id"],
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
    )

    conversation = conversations_collection.find_one(
        {"_id": result.inserted_id}
    )

    return {
        "conversation": serialize_conversation(
            conversation
        )
    }


@app.get(
    "/conversations/{conversation_id}/messages"
)
async def get_conversation_messages(
    conversation_id: str,
    user=Depends(get_current_user),
):
    conversation = conversation_owned_by_user(
        conversation_id,
        user["_id"],
    )

    messages = messages_collection.find(
        {
            "conversation_id": conversation["_id"]
        }
    ).sort(
        "created_at",
        ASCENDING,
    )

    return {
        "messages": [
            serialize_message(doc)
            for doc in messages
        ]
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user=Depends(get_current_user),
):
    conversation = conversation_owned_by_user(
        conversation_id,
        user["_id"],
    )

    messages_collection.delete_many(
        {
            "conversation_id": conversation["_id"]
        }
    )

    conversations_collection.delete_one(
        {
            "_id": conversation["_id"],
            "user_id": user["_id"],
        }
    )

    return {
        "message": "Conversation deleted"
    }


# ============================================================
# CHAT API
# ============================================================

@app.post("/chat")
async def chat_endpoint(
    chat_query: ChatQuery,
    user=Depends(get_current_user),
):
    user_query = chat_query.query.strip()

    if not user_query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    # --------------------------------------------------------
    # 1. Get existing conversation OR create one.
    # --------------------------------------------------------

    if chat_query.conversation_id:
        conversation = conversation_owned_by_user(
            chat_query.conversation_id,
            user["_id"],
        )
    else:
        now = datetime.now(timezone.utc)

        result = conversations_collection.insert_one(
            {
                "user_id": user["_id"],
                "title": "New Chat",
                "created_at": now,
                "updated_at": now,
            }
        )

        conversation = conversations_collection.find_one(
            {"_id": result.inserted_id}
        )

    # --------------------------------------------------------
    # 2. Get history BEFORE saving the current message.
    # --------------------------------------------------------

    history = build_history(
        conversation["_id"],
        limit=12,
    )

    # --------------------------------------------------------
    # 3. Save current user message.
    # --------------------------------------------------------

    messages_collection.insert_one(
        {
            "conversation_id": conversation["_id"],
            "user_id": user["_id"],
            "role": "user",
            "content": user_query,
            "created_at": datetime.now(timezone.utc),
        }
    )

    # --------------------------------------------------------
    # 4. Fast greeting path.
    # --------------------------------------------------------

    greetings = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "how are you",
    ]

    query_lower = user_query.lower()

    is_greeting = any(
        query_lower == greeting
        or query_lower.startswith(greeting + " ")
        for greeting in greetings
    )

    if is_greeting:
        formatted_result = (
            "👋 Hello! How can I help you today?"
        )

    else:
        # ----------------------------------------------------
        # 5. Prepare history + current question.
        # ----------------------------------------------------

        if history == "No previous messages.":
            question_for_rag = user_query
        else:
            question_for_rag = (
                "Recent conversation history:\n"
                f"{history}\n\n"
                "Current user question:\n"
                f"{user_query}"
            )

        # ----------------------------------------------------
        # 6. Run blocking RAG work in a threadpool.
        #
        # This keeps FastAPI's async event loop responsive,
        # while RAG_LOCK prevents concurrent FAISS operations.
        # ----------------------------------------------------

        try:
            formatted_result = await run_in_threadpool(
                run_rag,
                question_for_rag,
            )

        except Exception as exc:
            print("========== RAG ERROR ==========")
            print(f"{type(exc).__name__}: {exc}")
            print("================================")

            raise HTTPException(
                status_code=500,
                detail=(
                    "Unable to generate the healthcare "
                    "response. Please try again."
                ),
            )

    # --------------------------------------------------------
    # 7. Save assistant response.
    # --------------------------------------------------------

    messages_collection.insert_one(
        {
            "conversation_id": conversation["_id"],
            "user_id": user["_id"],
            "role": "assistant",
            "content": formatted_result,
            "created_at": datetime.now(timezone.utc),
        }
    )

    # --------------------------------------------------------
    # 8. First real question becomes conversation title.
    # --------------------------------------------------------

    title = conversation["title"]

    if title == "New Chat":
        title = (
            user_query[:40]
            + ("..." if len(user_query) > 40 else "")
        )

    # --------------------------------------------------------
    # 9. Update conversation metadata.
    # --------------------------------------------------------

    updated_conversation = (
        conversations_collection.find_one_and_update(
            {
                "_id": conversation["_id"],
                "user_id": user["_id"],
            },
            {
                "$set": {
                    "title": title,
                    "updated_at": datetime.now(
                        timezone.utc
                    ),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
    )

    # --------------------------------------------------------
    # 10. Return the same JSON contract used by React.
    # --------------------------------------------------------

    return {
        "conversation_id": str(
            updated_conversation["_id"]
        ),
        "conversation": serialize_conversation(
            updated_conversation
        ),
        "response": formatted_result,
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Healthcare Assistant API is running",
    }


# ============================================================
# STARTUP CHECK
# ============================================================

@app.on_event("startup")
async def startup_check():
    try:
        mongo_client.admin.command("ping")

        print("✅ MongoDB connection successful")
        print(f"✅ Database: {MONGODB_DB_NAME}")
        print("✅ FAISS vector store loaded")
        print("✅ FAISS OpenMP threads: 1")
        print("✅ Tokenizer parallelism: disabled")
        print(f"✅ Groq model: {GROQ_MODEL}")
        print("✅ RAG chain initialized")
        print("✅ Authentication system ready")
        print("✅ Conversation memory ready")
        print()
        print("⚠️ Start without --reload while testing:")
        print(
            "   uvicorn api:app --host 0.0.0.0 --port 8000"
        )

    except Exception as exc:
        print(
            f"⚠️ Startup check failed: "
            f"{type(exc).__name__}: {exc}"
        )
