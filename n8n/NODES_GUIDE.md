# Brainware Customer Care & Booking Assistant - Node Guide

This guide explains every node in `customer_care_booking_assistant.json`: what it is, what it does here, and how it connects to the others.

## The big picture

A visitor types a message in the chat. The **AI Agent** decides what to do:

- If the question is about Brainware University (fees, admission, BET, scholarships, contacts), it asks the **knowledge tool**, which searches the university text.
- If the visitor wants an appointment, it uses the **booking tools** in a fixed order: check duplicate, check availability, save booking.
- It remembers earlier messages through **memory**, so it doesn't ask for your name twice.

```
                     (sub-nodes that feed the agent)
 Chat Trigger -> Company Knowledge Document -> Simple Vector Store (insert) -> AI Agent
                                                  ^ Default Data Loader                    ^ OpenAI Chat Model
                                                  ^ Recursive Text Splitter                ^ Window Buffer Memory
                                                  ^ Embeddings OpenAI                      ^ Company Services Info (tool)
                                                                                                  ^ Knowledge Retriever
                                                                                           ^ Check Availability (tool)
                                                                                           ^ Check Duplicate Booking (tool)
                                                                                           ^ Save Booking (tool)
                                                                                           ^ List Bookings (tool)
```

Node types: **main nodes** pass data left to right. **Sub-nodes** (models, memory, tools, loaders) plug into a main node from below and provide a capability to it.

---

## 1. Entry and data flow nodes

### Chat Trigger
- **Type:** Chat Trigger (starts the workflow)
- **Purpose:** Receives each chat message and starts a run. It provides `chatInput` (the message), `sessionId` (identifies the conversation) and `action`.
- **Settings that matter:** `public: true` with hosted chat, so the workflow can be published and used from a shareable chat link. In the editor, use the **Open chat** button.
- **Connects to:** Company Knowledge Document.

### Company Knowledge Document
- **Type:** Edit Fields (Set)
- **Purpose:** Holds the university knowledge text (programmes, fees, admissions, BET, scholarships, contacts) in a field named `knowledge`.
- **Role in the flow:** It passes one item down the chain so the vector store step runs. Note: the text that is actually indexed is the copy stored inside the **Default Data Loader** node (see below). Edit the text there.
- **Connects to:** Simple Vector Store.

### Simple Vector Store (insert mode)
- **Type:** Simple Vector Store, operation "Insert Documents"
- **Purpose:** Turns the knowledge text into embeddings and saves them in memory under the key `brainware_demo_kb`.
- **Settings that matter:** `clearStore: true` wipes and reloads the store on every message, so it is never stale. `Always Output Data` is on, because insert returns no items and the agent must still run afterwards.
- **Sub-nodes it uses:** Default Data Loader (documents) and Embeddings OpenAI (embeddings).
- **Connects to:** AI Agent.

---

## 2. Knowledge (RAG) sub-nodes

RAG means "retrieval-augmented generation": find the relevant text first, then let the model answer from it.

### Default Data Loader
- **Type:** Default Data Loader
- **Purpose:** Converts the knowledge text into document objects the vector store can embed.
- **Settings that matter:** data type JSON, mode "Load Specific Data", text splitting "Custom" (uses the splitter below). The JSON field contains the full university text as a fixed value, because expressions are not reliable inside sub-nodes. **Edit the knowledge text here.**
- **Uses:** Recursive Text Splitter.

### Recursive Text Splitter
- **Type:** Recursive Character Text Splitter
- **Purpose:** Cuts the long text into chunks so searching returns small relevant pieces instead of the whole document.
- **Settings:** chunk size 1000 characters, overlap 200 (so a sentence cut at a boundary still appears whole in one chunk).

### Embeddings OpenAI
- **Type:** Embeddings OpenAI
- **Purpose:** Converts text into number vectors so the search can find chunks by meaning, not exact words.
- **Model:** `text-embedding-3-small`.
- **Used by:** both Simple Vector Store (to store) and Knowledge Retriever (to search). It needs an OpenAI credential.

### Knowledge Retriever
- **Type:** Simple Vector Store, operation "Retrieve Documents (As Vector Store for Chain/Tool)"
- **Purpose:** Searches the stored vectors that the insert node created. The memory key `brainware_demo_kb` must match the insert node.
- **Feeds:** Company Services Info.

### Company Services Info
- **Type:** Vector Store Question Answer Tool
- **Purpose:** The agent's "look it up" tool for university facts. It takes the agent's question, searches through Knowledge Retriever (top 4 chunks), and answers from those chunks with its own model call.
- **Tool name the agent sees:** `company_services_info`. Its description tells the agent to always use it for factual Brainware questions.
- **Uses:** Knowledge Retriever and OpenAI Chat Model. **Connects to:** AI Agent as a tool.

---

## 3. The agent and its brain

### AI Agent
- **Type:** AI Agent (tools agent)
- **Purpose:** The decision maker. It reads the visitor's message, chooses which tool to call, reads the result, and writes the reply.
- **System message:** sets the persona (Brainware help desk), the rules (facts only from the knowledge tool, bookings only through the tools), the booking order, the list of bookable services, and the five details to collect (name, phone, service, date, time).
- **Prompt:** `{{ $('Chat Trigger').first().json.chatInput }}`.
- **Plugs in:** OpenAI Chat Model, Window Buffer Memory, and five tools.

### OpenAI Chat Model
- **Type:** OpenAI Chat Model
- **Purpose:** The language model that does the reasoning. It is shared by the AI Agent and by Company Services Info.
- **Model:** `gpt-4o-mini` by default. If it mixes up booking fields, try `gpt-4.1-mini` or `gpt-4o`.

### Window Buffer Memory
- **Type:** Simple Memory (Window Buffer Memory)
- **Purpose:** Gives the agent the last messages of the conversation so it remembers your name, phone and earlier answers.
- **Settings:** session ID "from input" (each chat session has its own memory), context window of 20 exchanges.
- **Limit:** it is stored in n8n's memory, so it resets if you clear the chat or restart n8n.

---

## 4. Booking tools (Code Tool nodes)

All four share the same small "booking store": a list of bookings, plus three seeded sample bookings (`APT-0001` to `APT-0003`). They run JavaScript, call no external service, and reject bad input with clear messages. Each of the first three has an **input schema**, so the model is forced to fill in named fields.

### Check Availability (`check_availability`)
- **Input:** `date` (YYYY-MM-DD).
- **Does:** lists free hourly slots 09:00-16:00 for that date. Says "closed" for Sundays and "fully booked" when no slot is left.

### Check Duplicate Booking (`check_duplicate_booking`)
- **Input:** `customer`, `service`, `date`.
- **Does:** reports a duplicate when the same customer already has a confirmed booking for the same service on the same date. The agent must call this before saving.

### Save Booking (`save_booking`)
- **Input:** `customer`, `phone`, `service`, `date`, `time`.
- **Does:** validates everything (date format, known service, not a Sunday, valid hourly slot), refuses duplicates and slot conflicts, then creates a new reference like `APT-0004`.
- **Valid services:** Admission Counselling, Campus Tour, Hostel Enquiry, Exam Support, Scholarship Guidance, Fee Payment Assistance.

### List Bookings (`list_bookings`)
- **Input:** none.
- **Does:** prints every booking as `ref | customer | phone | service | date time | status`, sorted by date and time.

**Where bookings live:** in the workflow's static data. They persist between chats only while the workflow is **Published**. In the editor, each test run resets them.

---

## 5. Sticky notes
- **Sticky Note (green):** "Before you demo" checklist (credentials, how to chat, resets).
- **Sticky Note1 (blue):** how the n8n nodes map to the Python stages A-F in this repo.

---

## Typical flows

**Question:** "How can I take admission?"
Chat Trigger -> Set -> Simple Vector Store (reloads text) -> AI Agent -> calls `company_services_info` -> Knowledge Retriever finds chunks -> answer.

**Booking:** "Book Admission Counselling for Rajatava Ghosh, phone 12345678, next Monday at 10:00."
AI Agent -> `check_duplicate_booking` -> `check_availability` -> `save_booking` -> replies with `APT-XXXX`.

## Before running
1. Attach an OpenAI credential to **OpenAI Chat Model** and **Embeddings OpenAI**.
2. Open the chat (editor) or publish and use the chat link.
3. To see bookings, type "List all bookings".
