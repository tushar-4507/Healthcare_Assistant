# # pyright: reportUndefinedVariable=false
import os
import re
from dotenv import load_dotenv, find_dotenv
from langchain_core.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv(find_dotenv())

# ---- Custom Prompt Template ----
CUSTOM_PROMPT_TEMPLATE = """
You are a helpful English healthcare assistant chatbot.

Follow this structured answer format for every query:

If question is about a **disease**:
**Overview:** Short and clear explanation.  
**Symptoms:** Bullet points listing major symptoms.  
**Advice:** One short health suggestion.

If about **treatment**:
**Overview:** Short summary.  
**Treatment Options:** Bullet list of treatments.  
**Advice:** Suggest consulting a doctor.

If about **causes or prevention**:
**Overview:** Simple explanation.  
**Causes / Prevention:** Bullet list.  
**Advice:** One short line of general advice.

If about **general meaning**:
**Overview:** Simple definition.  
**Key Points:** Bullet list.  
**Advice:** End with awareness note.

---

Context:
{context}

Question:
{question}

Answer:
"""

def set_custom_prompt(template):
    return PromptTemplate(template=template, input_variables=["context", "question"])

# ---- Load FAISS Vectorstore ----
DB_FAISS_PATH = "vectorstore/db_faiss"
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
db = FAISS.load_local(DB_FAISS_PATH, embedding_model, allow_dangerous_deserialization=True)

# ---- QA Chain ----
qa_chain = RetrievalQA.from_chain_type(
    llm = ChatGroq(
    model_name="openai/gpt-oss-20b",
    temperature=0.1,
    groq_api_key=GROQ_API_KEY,
    timeout=30,
    max_retries=1,
),
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={'k': 2}),
    return_source_documents=True,  # Important used for debugging or safety
    chain_type_kwargs={'prompt': set_custom_prompt(CUSTOM_PROMPT_TEMPLATE)}
)

# ---- Format of a Model Output ----
def format_response(text: str) -> str:
    """Cleans and structures the chatbot's response for neat display."""
    text = text.replace("**", "").replace("###", "").strip()
    sections = {
        "Overview:": "🩺 Overview:",
        "Symptoms:": "• Symptoms:",
        "Treatment Options:": "💊 Treatment Options:",
        "Causes / Prevention:": "⚠️ Causes / Prevention:",
        "Key Points:": "📘 Key Points:",
        "Advice:": "✅ Advice:"
    }
    for key, value in sections.items():
        text = re.sub(rf"\b{re.escape(key)}", f"\n{value}", text)
    text = re.sub(r"\* ", "• ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()

# ---- Detect Unwanted & Invalid Input ----
def is_invalid_input(user_input: str) -> bool:
    """Detects if user input is gibberish or meaningless."""
    words = user_input.strip().split()
    if len(words) < 2:
        return True
    if not any(char.isalpha() for char in user_input):
        return True
    gibberish = ["hddhh", "wjar", "xxxx", "asdf", "qwerty"]
    if any(g in user_input.lower() for g in gibberish):
        return True
    return False

# ---- Main Interaction ----
if __name__ == "__main__":
    print("🩺 Healthcare Assistant Chatbot\n----------------------------------")

    while True:
        user_query = input("\nEnter your health question (or type 'exit' to quit): ").strip()
        if user_query.lower() in ["exit", "quit"]:
            print("👋 Goodbye! Take care of your health.")
            break

        # --- Handle greetings ---
        greetings = ["hi", "hello", "hey", "good morning", "good evening", "good afternoon"]
        if any(user_query.lower().startswith(greet) for greet in greetings):
            print("👋 Hello! How can I help you today?")
            continue

        # --- Detect invalid input ---
        if is_invalid_input(user_query):
            print("⚠️ Something went wrong. Please enter a valid health-related question.")
            continue

        try:
            # --- Check for relevant documents first ---
            retriever = db.as_retriever(search_kwargs={'k': 2})
            relevant_docs = retriever.get_relevant_documents(user_query)

            if not relevant_docs:
                print("❌ Sorry, I don't have enough information to answer that.")
                continue

            # --- Call QA chain only if relevant docs exist ---
            response = qa_chain.invoke({'query': user_query})
            raw_result = response.get("result", "").strip()

            # Safety check: if result is empty or very short
            if not raw_result or len(raw_result) < 20:
                print("❌ Sorry, I don't have enough information to answer that.")
                continue

            formatted = format_response(raw_result)
            print("\nRESULT:", formatted)

        except Exception as e:
            print("❌ Error while generating response:", str(e))
