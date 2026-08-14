import asyncio
import time
import os
import sys
# Ensure project root is on sys.path so `src` imports resolve when Chainlit
# executes the module from a different working directory.
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

import chainlit as cl
from src.chroma_client import get_chroma_client
from src.provider_clients import SarvamClient, EmbeddingClient, RerankerClient
from src.rl_logger import save_feedback
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

import sqlite3

# ==========================================
# 0. AUTOMATICALLY BUILD DATABASE TABLES
# ==========================================
def setup_sqlite_database():
    conn = sqlite3.connect("jonaki_history.db")
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            "id" TEXT PRIMARY KEY,
            "identifier" TEXT NOT NULL UNIQUE,
            "metadata" TEXT NOT NULL,
            "createdAt" TEXT
        );
        CREATE TABLE IF NOT EXISTS threads (
            "id" TEXT PRIMARY KEY,
            "createdAt" TEXT,
            "name" TEXT,
            "userId" TEXT,
            "userIdentifier" TEXT,
            "tags" TEXT,
            "metadata" TEXT,
            FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS steps (
            "id" TEXT PRIMARY KEY,
            "name" TEXT NOT NULL,
            "type" TEXT NOT NULL,
            "threadId" TEXT NOT NULL,
            "parentId" TEXT,
            "disableFeedback" INTEGER NOT NULL DEFAULT 0,
            "streaming" INTEGER NOT NULL,
            "waitForAnswer" INTEGER,
            "isError" INTEGER,
            "metadata" TEXT,
            "tags" TEXT,
            "input" TEXT,
            "output" TEXT,
            "createdAt" TEXT,
            "start" TEXT,
            "end" TEXT,
            "generation" TEXT,
            "showInput" TEXT,
            "language" TEXT,
            "indent" INTEGER,
            "defaultOpen" INTEGER,
            "autoCollapse" INTEGER
        );
        CREATE TABLE IF NOT EXISTS elements (
            "id" TEXT PRIMARY KEY,
            "threadId" TEXT,
            "type" TEXT,
            "url" TEXT,
            "chainlitKey" TEXT,
            "name" TEXT NOT NULL,
            "display" TEXT,
            "objectKey" TEXT,
            "size" TEXT,
            "page" INTEGER,
            "language" TEXT,
            "forId" TEXT,
            "mime" TEXT
        );
        CREATE TABLE IF NOT EXISTS feedbacks (
            "id" TEXT PRIMARY KEY,
            "forId" TEXT NOT NULL,
            "threadId" TEXT NOT NULL,
            "value" INTEGER NOT NULL,
            "comment" TEXT
        );
    """)
    conn.commit()
    conn.close()

# Run it immediately before Chainlit connects
setup_sqlite_database()

@cl.data_layer
def get_data_layer():
    return SQLAlchemyDataLayer(conninfo="sqlite+aiosqlite:///jonaki_history.db")

from typing import Optional

@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> Optional[cl.User]:
    if (username, password) == ("student", "1234"):
        return cl.User(identifier="student", metadata={"role": "class_3"})
    return None

# ==========================================
# RESUME LOGIC (RESTORES MEMORY)
# ==========================================
from chainlit.types import ThreadDict

@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    old_messages = []
    for step in thread["steps"]:
        if step["type"] == "user_message":
            old_messages.append({"role": "user", "content": step["output"]})
        elif step["type"] == "assistant_message":
            old_messages.append({"role": "assistant", "content": step["output"]})

    cl.user_session.set("message_history", old_messages)

# ==========================================
# CLIENT INITIALIZATION
# ==========================================
_chroma_client = get_chroma_client()
try:
    _collection = _chroma_client.get_collection(name="jonaki_assamese")
except Exception:
    _collection = None

print("Loading API Clients...")
_sarvam = SarvamClient()

print("Loading local AI models into memory (This will take a minute on CPU)...")
_embedder = EmbeddingClient()
_reranker = RerankerClient()
_embedder._ensure_model() # Force it to load into RAM now
_reranker._ensure_model() # Force it to load into RAM now
print("✅ Models loaded successfully! Jonaki is ready.")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def _class_label_in_assamese(class_code: str, source_file: str) -> str:
    if not class_code or class_code == "unknown":
        if "Class_III" in source_file or "Class III" in source_file:
            class_code = "III"
        elif "Class_IV" in source_file or "Class IV" in source_file:
            class_code = "IV"

    mapping = {
        "III": "তৃতীয় শ্ৰেণীৰ পৰিৱেশ",
        "IV": "চতুৰ্থ শ্ৰেণীৰ পৰিৱেশ",
        "3": "তৃতীয় শ্ৰেণীৰ পৰিৱেশ",
        "4": "চতুৰ্থ শ্ৰেণীৰ পৰিৱেশ",
    }
    return mapping.get(class_code, None)

def format_assamese_citation(meta: dict) -> str:
    source = meta.get("source_file", "অজানা পুথি")
    page = meta.get("page_number", "অজানা")
    class_code = meta.get("class", "unknown")

    class_label = _class_label_in_assamese(class_code, source)
    if class_label:
        return f"{class_label} পুথিৰ {page} নং পৃষ্ঠাৰ পৰা"
    return f"{source} পুথিৰ {page} নং পৃষ্ঠাৰ পৰা"

def _extract_answer_from_sarvam_response(resp) -> str:
    if hasattr(resp, 'choices') and len(resp.choices) > 0:
        message = resp.choices[0].message
        if hasattr(message, 'content'):
            return message.content

    if isinstance(resp, dict):
        if "choices" in resp and resp["choices"]:
            choice = resp["choices"][0]
            if isinstance(choice, dict):
                msg = choice.get("message", {})
                return msg.get("content", "") if isinstance(msg, dict) else msg
        if "text" in resp:
            return resp["text"]

    return str(resp)


# ==========================================
# CHAT START (NEW: Initializes Memory Buffer)
# ==========================================
@cl.on_chat_start
async def start():
    # Initialize an empty array for memory when a new session starts
    cl.user_session.set("message_history", [])


# ==========================================
# MAIN MESSAGE & ROUTER
# ==========================================
@cl.on_message
async def main(message: cl.Message):
    print(f"DEBUG: Message received: {message.content}")

    # 1. Retrieve the Rolling Memory Buffer
    history = cl.user_session.get("message_history", [])

    # 2. Add the user's raw message to memory immediately
    history.append({"role": "user", "content": message.content})

    user_input = message.content.strip().lower()
    small_talk_keywords = [
        "নমস্কাৰ", "হেল্ল", "হাই", "তোমাৰ নাম কি", "তুমি কোন", "কেনে আছা", "ভালনে", "ধন্যবাদ", "মই বুজিছোঁ", "সুপ্ৰভাত", "শুভৰাত্ৰি", "হেলো", "ভাল", "বিদায়",
        "hello", "hi", "how are you", "your name", "who are you", "thank you", "thanks", "i understand", "good morning", "good night", "hey"
    ]
    is_small_talk = any(keyword in user_input for keyword in small_talk_keywords)

    answer = ""

    start_time = time.time()

    if is_small_talk:
        print("DEBUG: Routing to Small Talk...")
        small_talk_system_prompt = (
            "আপুনি 'জোনাকী', তৃতীয় আৰু চতুৰ্থ শ্ৰেণীৰ ছাত্ৰ-ছাত্ৰীৰ মৰমীয়াল AI শিক্ষক। "
            "নিৰ্দেশনা: "
            "1. ছাত্ৰজনক মৰমেৰে উত্তৰ দিয়ক। "
            "2. যদি নাম সোধে, কওক যে আপোনাৰ নাম জোনাকী। "
            "3. কোনো কিতাপৰ কথা উল্লেখ নকৰিব আৰু 'মই তোমাৰ পাঠ্যপুথিখন চাই...' বুলি নক'ব। "
            "4. উত্তৰটোৰ শেষত সদায় এইদৰে সুধিব: 'আজি আমি পৰিৱেশ পুথিৰ কি বিষয়ৰ বিষয়ে আলোচনা কৰিম বাৰু?'"
        )

        # 3a. Combine System Prompt with the Rolling Memory Window (last 4 messages)
        messages = [{"role": "system", "content": small_talk_system_prompt}] + history[-4:]

        try:
            resp = _sarvam.chat(messages)
            answer = _extract_answer_from_sarvam_response(resp)
        except Exception:
            answer = "নমস্কাৰ! মই জোনাকী। আজি আমি পৰিৱেশ পুথিৰ কি বিষয়ৰ বিষয়ে আলোচনা কৰিম বাৰু?"

        end_time = time.time()
        print(f"⏱️ SMALL TALK LATENCY: {round(end_time - start_time, 2)} seconds")

        await cl.Message(content=answer).send()

    else:
        print("DEBUG: Routing to RAG Pipeline...")
        try:

            # 2. Convert the user's question into a 1024-dimension vector FIRST
            question_vector = await asyncio.to_thread(
                _embedder.get_embeddings, [message.content]
            )


            # Query ChromaDB using the VECTOR, fetching 10 results
            result = _collection.query(
                query_embeddings=question_vector,
                n_results=10,
                include=["metadatas", "documents"]
            )

            # 4. Extract the documents and metadata
            retrieved_metas = (result.get("metadatas") or [[]])[0]
            retrieved_docs = (result.get("documents") or [[]])[0]
            
            # 5. Pass them through our new Reranker to get the absolute best 3!
            best_docs = await asyncio.to_thread(
                _reranker.rerank, message.content, retrieved_docs, top_k=3
            )


            # 6. Re-align metadata with the reranked documents for accurate citations!
            metadatas = []
            documents = []
            for doc in best_docs:
                if doc in retrieved_docs:
                    idx = retrieved_docs.index(doc)
                    documents.append(doc)
                    metadatas.append(retrieved_metas[idx])
                    
        except Exception as e:
            await cl.Message(content=f"Error querying vector DB: {e}").send()
            metadatas = []
            documents = []

        # Create context from the best docs
        context = "\n\n".join([d for d in documents if d])

        # 7. Create the System Prompt
        base_system_prompt = (
            "আপুনি 'জোনাকী', তৃতীয় আৰু চতুৰ্থ শ্ৰেণীৰ ছাত্ৰ-ছাত্ৰীৰ এজন মৰমীয়াল শিক্ষক।"
            "নিৰ্দেশনাসমূহ: "
            "১. যদি প্ৰশ্নটো পৰিৱেশ বিজ্ঞান (EVS) ৰ লগত জড়িত, তেন্তে উত্তৰটো সদায়ে এইদৰে আৰম্ভ কৰিব: 'মই তোমাৰ পাঠ্যপুথিখন চাই মেলি যিখিনি পালোঁ, তাৰ ওপৰত ভিত্তি কৰি উত্তৰটো এনেধৰণৰ—'"
            "২. যদি প্ৰশ্নটো পৰিৱেশ বিজ্ঞানৰ বাহিৰে আন কোনো বিষয়ৰ হয় (যেনে অংক, খেল আদি), তেন্তে উত্তৰটোৰ আৰম্ভণিতে কেৱল ক'ব: 'মই আচলতে পৰিৱেশ বিজ্ঞানৰহে শিক্ষক, তথাপিও মই তোমাক সহায় কৰিবলৈ চেষ্টা কৰিম।' আৰু তাৰ পিছত উত্তৰটো দিব। "
            "৩. উত্তৰ দিওঁতে কোনো কঠিন বা বৈজ্ঞানিক শব্দ (যেনে- অক্সিজেন, বায়ুমণ্ডল, কাৰ্বন-ডাই-অক্সাইড) ব্যৱহাৰ নকৰিব। যদি তেনে শব্দ ব্যৱহাৰ কৰিবলগীয়া হয়, তেন্তে সেইবোৰ পোনপটীয়া সংজ্ঞাৰ সলনি সৰল বাক্যৰে বুজাই দিব "
            "৪. ৯-১০ বছৰীয়া শিশুৱে সহজে বুজি পোৱাকৈ অতি সৰল ভাষাত উত্তৰ দিব।"
        )

        # 3b. INJECT CONTEXT INTO SYSTEM PROMPT (Prevents memory bloat)
        full_system_prompt = f"{base_system_prompt}\n\nপ্ৰাসংগিক তথ্য (Textbook Context):\n{context}"

        # 3c. Combine System Prompt with the Rolling Memory Window (last 4 messages)
        messages = [{"role": "system", "content": full_system_prompt}] + history[-4:]

        try:
            resp = await asyncio.to_thread(_sarvam.chat, messages)
            answer = _extract_answer_from_sarvam_response(resp)
        except Exception:
            answer = documents[0] if documents else "মই কোনো প্ৰাসংগিক তথ্য পোৱা নাই।"

        await cl.Message(content=answer).send()

        end_time = time.time()
        print(f"⏱️ RAG VECTOR LATENCY: {round(end_time - start_time, 2)} seconds")

        # --- NEW LOGIC: Check if it's an Out-of-Domain answer ---
        out_of_domain_phrases = [
            "মই আচলতে পৰিৱেশ বিজ্ঞানৰহে শিক্ষক",
            "মই আচলতে পৰিৱেশ বিজ্ঞানৰ শিক্ষক",
            "মই আচলতে পৰিৱেশ বিজ্ঞানৰ (EVS) শিক্ষক",
            "আচলতে, মই পৰিৱেশ বিজ্ঞানৰ শিক্ষক"
        ]
        is_out_of_domain = any(phrase in answer for phrase in out_of_domain_phrases)

        # Only print citations if it is an actual EVS question
        if not is_out_of_domain:
            if metadatas:
                citation_lines = []
                for meta in metadatas:
                    citation_lines.append(format_assamese_citation(meta))
                citation_text = "\n".join([f"- {c}" for c in citation_lines])
                await cl.Message(content=f"উৎসসমূহ:\n{citation_text}").send()
            else:
                await cl.Message(content="উৎসসমূহ উপলব্ধ নহয়।").send()

        # Save question/answer for RLHF buttons
        cl.user_session.set("current_question", message.content)
        cl.user_session.set("current_answer", answer)
        
        actions = [
            cl.Action(name="feedback_up", payload={"value": "helpful"}, label="👍 Helpful"),
            cl.Action(name="feedback_down", payload={"value": "not_helpful"}, label="👎 Not Helpful")
        ]
        feedback_msg = await cl.Message(
            content="Did you like my answer?",
            actions=actions
        ).send()
        cl.user_session.set("feedback_msg_id", feedback_msg.id)

    # 4. Save the AI's final answer to the Memory Buffer
    if answer:
        history.append({"role": "assistant", "content": answer})
        cl.user_session.set("message_history", history)


# ==========================================
# RLHF & STARTERS (UNCHANGED)
# ==========================================
@cl.action_callback("feedback_up")
async def on_feedback_up(action: cl.Action):
    question = cl.user_session.get("current_question", "Unknown")
    answer = cl.user_session.get("current_answer", "Unknown")
    save_feedback(question, answer, "Helpful (👍)")

    msg_id = cl.user_session.get("feedback_msg_id")
    if msg_id:
        updated_msg = cl.Message(
            id=msg_id,
            content="Did you like my answer? \n\n**✅ You selected: 👍 Helpful**"
        )
        updated_msg.actions = []
        await updated_msg.update()

    await cl.Message(content="Thank you! I will keep up the good work. 😊").send()

@cl.action_callback("feedback_down")
async def on_feedback_down(action: cl.Action):
    question = cl.user_session.get("current_question", "Unknown")
    answer = cl.user_session.get("current_answer", "Unknown")
    save_feedback(question, answer, "Not Helpful (👎)")

    msg_id = cl.user_session.get("feedback_msg_id")
    if msg_id:
        updated_msg = cl.Message(
            id=msg_id,
            content="Did you like my answer? \n\n**✅ You selected: 👎 Not Helpful**"
        )
        updated_msg.actions = []
        await updated_msg.update()

    await cl.Message(content="Thanks for the feedback. I will try to learn and improve! 📝").send()

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="গছৰ উপকাৰিতা",
            message="গছ আমাৰ বাবে কিয় প্ৰয়োজনীয়?",
            icon="/public/tree_icon.svg",
            ),
        cl.Starter(
            label="স্বাস্থ্য আৰু সুৰক্ষা",
            message="সুস্বাস্থ্যৰ বাবে আমি কি কি কৰা উচিত?",
            icon="/public/Health_icon.svg",
            ),
        cl.Starter(
            label="আমাৰ বিদ্যালয়",
            message="আমাৰ বিদ্যালয়ত আমি কি কি কৰা উচিত?",
            icon="/public/school_icon.svg",
            ),
        cl.Starter(
            label="আমাৰ অধিকাৰ",
            message="আমাৰ অধিকাৰ সম্পৰ্কে আমি কি কি জানিব?",
            icon="/public/rights_icon.svg",
            )
    ]