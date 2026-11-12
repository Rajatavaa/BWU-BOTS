# Brainware Help Desk Assistant — AI chatbot with RAG + booking tools

An AI assistant for the **Brainware University help desk**, built two ways so you can compare the approaches:

1. **Python** — five small scripts (Stages A–E) that grow a plain chatbot into a full agent that answers university questions (RAG) and books appointments in Excel.
2. **n8n (low-code)** — one importable workflow with the same knowledge base and the same booking rules, built visually.

Both versions do exactly the same job:

- **Answer questions** about Brainware University (programmes, fees, admissions, the BET entrance test, scholarships, contacts) using only the knowledge base — never invention.
- **Book appointments** (Admission Counselling, Campus Tour, Hostel Enquiry, Exam Support, Scholarship Guidance, Fee Payment Assistance) through strict, deterministic rules.

> The core idea: **the LLM decides what to do; the tools decide what is true.** The model can never invent a free slot, a price or a booking reference.

---

## What a chat looks like

```
You:     What are the fees for BTech CSE?
Agent:   The total programme fee for BTech CSE is Rs 5,79,600 for 4 years.
         Fees are subject to change - shall I confirm anything else?

You:     I'm Omar Diaz, 555-0134. Book Hostel Enquiry on Friday at 09:00.
Agent:   [checks availability -> free] [checks duplicates -> none]
         Booked: APT-0004 - Omar Diaz, Hostel Enquiry, Friday 09:00.
```

---

## Repository structure

```
├── data/
│   ├── brainware.md                  # the knowledge base (single source of truth for RAG)
│   └── bookings_python.xlsx          # demo booking store (auto-created, gitignored)
├── python/                           # Stages A–E (each runs standalone)
│   ├── common.py                     # shared helpers: config, business rules, Excel I/O
│   ├── reset_workbook.py             # reset the demo workbook (recreates seed bookings)
│   ├── stage_a_chatbot.py            # A: plain chatbot - hallucinates (why grounding matters)
│   ├── stage_b_rag_chatbot.py        # B: grounded answers + full RAG pipeline
│   ├── stage_c_customer_details.py   # C: chat -> structured, validated data (Pydantic)
│   ├── stage_d_agent_tools.py        # D: agent that calls tools (in-memory store)
│   └── stage_e_excel_booking.py      # E: full agent - checks + books in Excel
├── n8n/
│   ├── customer_care_booking_assistant.json   # importable n8n workflow
│   └── NODES_GUIDE.md                # what every n8n node does (read this after import)
└── .env.example                      # copy to .env and add your keys
```

### The stages, one concept each

| Stage | Run it to see | New concept |
|---|---|---|
| A | the bot **invent** answers about Brainware | plain LLM chat (Groq) |
| B | the same question answered **from the document**, two ways | grounding + RAG (chunk → embed → retrieve) |
| C | chat turned into a **validated form** (name, phone, service, date, time) | structured output (Pydantic) |
| D | the bot **call tools** live (`[agent → tool]` traces) | tools = deterministic functions |
| E | a real booking saved to **Excel** after all checks pass | persistence + verify-after-save |

---

## Quick start — Python

Requires Python 3.10+ and a Groq (free) API key; Stage B additionally needs an OpenAI key for embeddings.

```bash
# 1) install dependencies (uv fetches the right Python automatically)
#    https://docs.astral.sh/uv/getting-started/installation/
uv sync

# 2) add your keys - never commit .env
cp .env.example .env
#    GROQ_API_KEY    -> https://console.groq.com/keys
#    OPENAI_API_KEY  -> https://platform.openai.com/api-keys  (Stage B only)

# 3) run the stages in order
uv run python python/stage_a_chatbot.py
uv run python python/stage_b_rag_chatbot.py
uv run python python/stage_c_customer_details.py
uv run python python/stage_d_agent_tools.py
uv run python python/stage_e_excel_booking.py

# reset the demo workbook any time
uv run python python/reset_workbook.py
```

No `uv`? Plain pip works too:
`python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`

---

## Quick start — n8n

1. Open n8n (self-hosted is free; n8n Cloud works too) and import `n8n/customer_care_booking_assistant.json`.
2. Open the **OpenAI Chat Model** and **Embeddings OpenAI** nodes and attach your OpenAI credential (the only manual step - keys never travel inside the JSON).
3. Click **Open chat** and talk to the assistant. Or publish the workflow and share the hosted chat link.
4. New to n8n? Read `n8n/NODES_GUIDE.md` - it explains every node.

Three demo bookings are pre-seeded (APT-0001 to APT-0003). Bookings persist while the workflow is **active**; editor test runs reset them - that is the reset button.

---

## Things to try (both stacks)

| Try saying | You should see |
|---|---|
| "What scholarships do you offer?" | Facts from `data/brainware.md`, with a source-grounded answer |
| "Is the BET entrance test compulsory?" | Yes - 1 hour, 100 marks, MCQ |
| "Book Campus Tour for me, John Roy, 555-0190, Friday 11:00" | Availability check → duplicate check → confirmed with an APT-XXXX reference |
| "Maya Chen, Admission Counselling again on her booked date" | **Refused** - duplicate rule |
| "Book something Sunday" | **Refused** - closed Sundays, Mon-Sat offered |
| "Book 10:30" | **Refused** - only hourly starts 09:00-16:00 |
| "List all bookings" | The full table with references |

---

## Booking rules (identical in both stacks)

- Hourly start times **09:00-16:00**, Monday-Saturday; **closed Sundays**.
- **One appointment per slot** - an occupied date+time blocks the slot.
- **No duplicates** - same customer + same service + same date is refused.
- Booking references look like `APT-0004`, generated from the highest existing one.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `GROQ_API_KEY is missing` | Copy `.env.example` to `.env` in the repo root and paste your key. |
| `401` from a provider | Key pasted with quotes/spaces - re-paste it raw. |
| Groq says the model doesn't exist | Model ids drift; set a current one in `GROQ_MODEL` in `.env`. |
| Stage B asks for `OPENAI_API_KEY` | Groq has no embeddings - Stage B needs the OpenAI key. |
| Excel rows look odd | `uv run python python/reset_workbook.py` regenerates the workbook. |
| n8n: no bot reply | Check the Executions tab for errors; usually a missing OpenAI credential. |
| n8n: bookings vanish between tests | They only persist while the workflow is **active**; editor runs reset by design. |

---

## Credits

- Knowledge base: [Brainware University](https://www.brainwareuniversity.ac.in/) (crawled 2026-08-31, stored in `data/brainware.md`).
- Models: Groq (chat, Python path) and OpenAI (embeddings; chat in the n8n path).

License: [MIT](LICENSE)
