# Jonaki — RAG-Based Assamese AI Tutor (Architecture & Implementation Plan)

## Overview
Jonaki is an advanced Retrieval-Augmented Generation (RAG) assistant specifically bounded to Class 3 and 4 Environmental Science (পৰিৱেশ) for Assamese medium students. 
Instead of relying on heavy orchestration frameworks, Jonaki uses a custom, highly-optimized pipeline:
- **LLM**: Sarvam-30B (Inference endpoint via `provider_clients.py`)
- **Vision / OCR**: Sarvam-Vision (For Assamese textbook extraction)
- **Embeddings**: Sarvam-2B
- **Vector DB**: ChromaDB (Local persistent storage)
- **Stateful Memory**: SQLite via Chainlit SQLAlchemy Data Layer
- **UI & Orchestration**: Chainlit (with custom CSS branding)

---

## 1. Project Architecture & Directory Structure

```text
Major Project/
|— .chainlit/               # Chainlit configuration and translations
    |— config.toml          # UI settings (HTML rendering enabled)
|— public/                  # Frontend web assets
    |— gemini_theme.css     # Custom CSS overrides for Jonaki branding (Rubik Moonrocks font)
    |— theme_injector.js
|— chroma_db/               # Local Vector Database (Jonaki's factual memory)
|— data/                    # Raw materials and output datasets
    |— cleaned_text/
    |— pdfs/                # Source SCERT/SEBA Assamese PDFs
    |— split_pdfs/
    |— rlhf_feedback_dataset.csv # The RLHF Logger Output (Thumbs Up/Down data)
|— scripts/                 # One-time data pipeline scripts (Factory Floor)
    |— batch_ocr.py
    |— chunk_text.py
    |— clean_markdown.py
    |— split_pdf.py
    |— cloud_ingestion.py
    |— reset_chroma.py
    |— test_provider.py
|— src/                     # Live Application Engine
    |— chainlit_app.py      # Main application, Router, and UI logic
    |— chroma_client.py     # Database retrieval logic
    |— ingest_to_chroma.py  # Embedding logic
    |— provider_clients.py  # Sarvam API connection and error handling
    |— rl_logger.py         # Reinforcement learning data capture logic
|— textbook_chunks/         # Sliced textbook JSONL files
|— textbook_txt/            # Raw OCR markdown
|— .env                     # Secrets vault (API Keys, Auth Secrets)
|— PLAN.md                  # Project documentation
|— chainlit.md              # User welcome screen markdown
|— jonaki_history.db        # Automatically generated SQLite Chat History database
|— requirements.txt         # Dependency list

```

---

## 2. Secrets & Environment Variables

- **Do not hardcode credentials** in your scripts.
- Create a `.env` file in the project root containing:

    ```text
    SARVAM_API_KEY=your_actual_api_key_here
    CHAINLIT_AUTH_SECRET=jonaki_super_secret_key_2026
    ```

---

## 3. The Data Pipeline (Offline Processing)

1. **Source Material:** Place SCERT Assamese textbooks (Class III and IV EVS) in `data/pdfs/`.

2. **Splitting & OCR:** Run `scripts/split_pdf.py` followed by `scripts/batch_ocr.py` using Sarvam-Vision to extract Assamese text.

3. **Chunking:** Run `scripts/chunk_text.py` to break the text into overlapping semantic chunks, preserving metadata (Class, Chapter, Page Number).

4. **Vectorization:** Run `src/ingest_to_chroma.py` to convert chunks into Sarvam-2B embeddings and store them permanently in `chroma_db/`.

---

## 4. The Live Application (`src/chainlit_app.py`)

### A. Intent-Based Routing (Semantic Router)

To prevent the LLM from executing costly database searches for simple greetings, the application implements a Semantic Router.

- **Small Talk Route:** If the user inputs greetings (e.g., "নমস্কাৰ", "hello", "ধন্যবাদ"), the system bypasses RAG and responds using a friendly, predefined persona prompt, steering the user back to educational topics.

- **EVS Route:** All other queries are pushed through the RAG pipeline.

### B. The RAG Pipeline

1. **Retrieval:** Queries ChromaDB for the top-5 most relevant chunks.

2. **Prompt Injection:** Combines the retrieved chunks with the strict "Jonaki Persona" system guardrail, preventing hallucinations or out-of-domain answers (e.g., Mathematics or Politics).

3. **Generation:** Calls Sarvam-30B to generate a child-friendly Assamese response.

4. **Citation:** Formats the `metadata` to output explicit page references (e.g., উৎসসমূহ: চতুৰ্থ শ্ৰেণীৰ পৰিৱেশ পুথিৰ...).

### C. Stateful Memory & Authentication

- **Data Persistence:** Uses Chainlit's `SQLAlchemyDataLayer` connected to a local `jonaki_history.db` SQLite file.

- **Authentication:** A mock authentication layer is implemented for the project defense.
    - **Username:** `student`
    - **Password:** `1234`

- **Session Resume:** The `@cl.on_chat_resume` hook allows students to click previous conversations in the sidebar and dynamically re-inject historical context into the LLM's memory.

### D. Reinforcement Learning from Human Feedback (RLHF)

- **UI Integration:** After every RAG-based educational answer, the system renders a "👍 Helpful" and "👎 Not Helpful" button pair.

- **Data Logging:** Handled by `src/rl_logger.py`, user clicks are instantly logged into `data/rlhf_feedback_dataset.csv`.

- **Purpose:** This captures real-time human preference data (User Query + AI Response + Rating), laying the groundwork for future model alignment and fine-tuning.

### 5. Execution Commands

To run the fully integrated Jonaki assistant locally:

```bash
# Ensure virtual environment is activated
chainlit run src/chainlit_app.py
```

***Note: Use `Ctrl + F5` in the browser to hard-refresh CSS changes if the UI does not update immediately.***