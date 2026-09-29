

```markdown
# TASK SPECIFICATION: Phase 2 - Two-Tier Workspace React UI

You are an expert Frontend Engineer. Build Phase 2 (React Frontend) for our Two-Tier RAG Application. The frontend connects to a PostgreSQL backend (Neon) using the 5 subjects created in Phase 1.

---

## 1. TECH STACK & PREREQUISITES
- **Framework:** React (Vite / Next.js App Router) with TypeScript
- **Styling:** Tailwind CSS + shadcn/ui (Lucide icons)
- **State Management:** Zustand or React Context (Global Workspace State)
- **Markdown Rendering:** `react-markdown` + `remark-gfm` (Supports AI streaming, code blocks, tables)
- **Icons:** `lucide-react`

---

## 2. DATABASE SCHEMA CONTEXT
Our Neon PostgreSQL database has the following structure:
- `users`: `id` (UUID), `email`
- `subjects`: `id` (UUID), `name`, `slug`, `vector_collection_name`, `description`
- `chat_sessions`: `id` (UUID), `user_id` (UUID), `subject_id` (UUID), `title`, `updated_at`
- `messages`: `id` (UUID), `session_id` (UUID), `sender` ('user'|'assistant'), `content`, `sources` (JSONB), `rag_metadata` (JSONB)

### Hardcoded Mock Data for Subjects (Until FastAPI Backend in Phase 3)
```json
[
  { "id": "11111111-1111-1111-1111-111111111111", "name": "Embedded System", "slug": "embedded-system", "description": "Microcontrollers, RTOS, low-level C/C++, hardware interfaces." },
  { "id": "22222222-2222-2222-2222-222222222222", "name": "Cloud Technology", "slug": "cloud-technology", "description": "AWS/Azure/GCP, Docker, Kubernetes, distributed systems." },
  { "id": "33333333-3333-3333-3333-333333333333", "name": "Digital Image Processing", "slug": "digital-image-processing", "description": "Spatial filtering, frequency domain, segmentation, computer vision." },
  { "id": "44444444-4444-4444-4444-444444444444", "name": "Digital Signal Processing", "slug": "digital-signal-processing", "description": "FFT/DFT, z-transforms, FIR/IIR digital filter design." },
  { "id": "55555555-5555-5555-5555-555555555555", "name": "Software Engineering", "slug": "software-engineering", "description": "System architecture, design patterns, SDLC, testing, DevOps." }
]

```

---

## 3. UI ARCHITECTURE & COMPONENT REQUIREMENTS

Build a **Two-Tier Navigation Architecture**:

### VIEW 1: Authentication Screen (Mandatory Gateway)

* Clean Login / Register Card.
* Simple state toggle (`isLoggedIn: boolean`).
* Once authenticated, store mock token and route to **VIEW 2 (Subject Hub)**.

### VIEW 2: Subject Hub (Landing / Workspace Selector)

* **Header:** Displays User Account Profile & Logout button.
* **Title:** "Select a Knowledge Base Workspace".
* **Grid Layout:** Render 5 subject cards based on the mock array.
* **Subject Card Elements:**
* Subject Icon (e.g., `Cpu` for Embedded, `Cloud` for Cloud, `Eye` for Image, `Activity` for Signal, `Code` for Software Engineering).
* Title & Description.
* Action Button: "Enter Workspace →".


* **Interaction:** Clicking a card sets `activeSubject` in state and transitions the view to **VIEW 3 (Subject Workspace)**.

### VIEW 3: Subject Workspace (Dedicated Chat Interface)

This view consists of a **Sidebar** and a **Main Chat Area**.

#### A. Left Sidebar (Subject-Scoped History)

* **Workspace Badge (Top):** Displays active subject name with a `← Switch Subject` button to return to View 2.
* **Action Button:** `+ New Chat` (Creates a fresh session within the active subject).
* **Session List:** Filters and displays past chats **ONLY** for `activeSubject.id`.
* **User Footer:** Shows active user email + Logout button.

#### B. Main Chat Window

* **Chat Header:**
* Displays current subject tag + active Chat Session title.
* Shows RAG status badge: `🟢 Index Active: [vector_collection_name]`.


* **Message List (Scrollable Container):**
* **User Message Bubble:** Right-aligned, dark primary background.
* **Assistant Message Bubble:** Left-aligned, muted background.
* Markdown rendering support (code snippets, bold, lists).
* **RAG Citation Accordion (Bottom of bubble):** Collapsible panel titled "📚 Retrieved Sources (X)". Shows source document title, page number, and similarity score snippet.




* **Input Area (Bottom Fixed):**
* Textarea with auto-expand / `Shift+Enter` for new line / `Enter` to send.
* "Send" button with loading/stop state.
* Quick Suggestion Pills above input (e.g., for Embedded: "Explain RTOS task scheduling vs interrupt service routines").



---

## 4. STATE MANAGEMENT SPECIFICATION

Create a `useWorkspaceStore` hook / context handling:

1. `currentUser`: `{ id, email } | null`
2. `activeSubject`: `Subject | null`
3. `activeSessionId`: `string | null`
4. `sessions`: `ChatSession[]` (Filtered by `activeSubject.id`)
5. `messages`: `Message[]` (Filtered by `activeSessionId`)
6. **Actions:**
* `login(email, password)`
* `selectSubject(subjectId)`
* `clearSubject()` (Returns to Hub)
* `createSession()`
* `selectSession(sessionId)`
* `sendMessage(content)` (Adds user message, triggers simulated assistant streaming response with dummy source citations)



---

## 5. MOCK AI STREAMING SIMULATOR

In the `sendMessage` function, simulate a real RAG streaming backend:

1. Instantly append User Message to the view.
2. Add an empty Assistant message with a loading indicator.
3. Stream token text chunks every 50ms (simulating Ollama token streaming).
4. Append mock source metadata once generation completes:
```json
"sources": [
  { "title": "Lecture_3_RTOS_Fundamentals.pdf", "page": 12, "score": 0.89 },
  { "title": "Embedded_Systems_Architecture_Ch2.pdf", "page": 45, "score": 0.82 }
]

```



---

## 6. INSTRUCTIONS FOR THE AI AGENT

1. Generate the modular folder structure under `src/`:
* `components/auth/`
* `components/hub/`
* `components/workspace/`
* `components/chat/`
* `context/` or `store/`
* `types/`


2. Ensure Tailwind CSS classes handle light/dark mode gracefully (default to modern dark UI).
3. Do not leave placeholder comments; generate complete, working TSX code for all views.

```

---
