# Brightlane Customer Care & Booking Assistant — one agent, two stacks

The companion repo for the workshop **"AI Agents, Chatbots & Business Automation"**
(the teaching outline lives in [`docs/AI_Agents_Technical_Teaching_Outline.pdf`](docs/AI_Agents_Technical_Teaching_Outline.pdf)).

You build the **same assistant twice** for **Brightlane Home Services** (a fictional home-care company):

1. **Low-code:** an [n8n](https://n8n.io) workflow — chat trigger → knowledge base (RAG) → AI Agent with four booking tools.
2. **Code:** Python — six small scripts (Stages A–F) that grow a plain chatbot into a LangChain agent that reads, checks and books appointments in an Excel sheet.

Everything the assistant does is **deterministic and re-runnable**: seed data is generated relative to *today*, so every demo works on any day, in front of any audience.

---

## The demo business (Brightlane Home Services)

All agents — in both stacks — enforce the same rules, on purpose. They make great teaching moments when the LLM *can't* just make things up:

- **Services & prices** come from one shared document: [`data/company_services.txt`](data/company_services.txt)
  (Home Deep Cleaning $149, Standard Cleaning $89, Plumbing $99, Electrical $99, HVAC $129, Appliance Repair $119 …).
- **Slots:** hourly start times `09:00`–`16:00`, Monday–Saturday, one technician per 60-minute slot.
- **Closed on Sundays** — any booking on a Sunday is refused with a friendly explanation.
- **Duplicate rule:** the same customer + same service + same date (case-insensitive) is refused.
- **Slot-conflict rule:** any confirmed booking already occupying `date + time` blocks the slot.
- **Booking references:** `APT-0001`, `APT-0002`, … generated from the highest existing ref.
- Three **seed bookings** (Maya Chen, Dmitri Volkov, Elena Petrova) are preloaded so the conflict and duplicate demos are ready to fire.

> The Excel file and the n8n store are **demo storage**, not production databases. Reset them independently.

---

## Repository layout

```
├── data/
│   ├── company_services.txt          # single source of truth for RAG (both stacks)
│   └── bookings_python.xlsx          # Stage E/F demo workbook (gitignored, auto-created)
├── python/                           # Stages A–F
│   ├── common.py                     # shared helpers: .env, business rules, Excel I/O
│   ├── reset_workbook.py             # recreate data/bookings_python.xlsx with seed rows
│   ├── stage_a_chatbot.py            # A: first LLM chat (Groq)
│   ├── stage_b_rag_chatbot.py        # B: document-grounded chat (RAG)
│   ├── stage_c_customer_details.py   # C: structured intake (Pydantic)
│   ├── stage_d_agent_tools.py        # D: LangChain agent + tools (in-memory)
│   ├── stage_e_excel_booking.py      # E: same agent, booking in Excel
│   └── stage_f_observe_debug.py      # F: scripted scenarios, traces, LangSmith
├── n8n/
│   └── customer_care_booking_assistant.json   # importable n8n workflow
├── docs/                             # the teaching outline (PDF)
├── .env.example                      # copy to .env, paste YOUR keys
├── pyproject.toml + uv.lock          # uv project definition (locked deps)
└── requirements.txt                  # plain-pip fallback
```

### How the stages map to the n8n workflow

| Python stage | n8n counterpart | Concept |
|---|---|---|
| A `stage_a_chatbot.py` | Chat Trigger + AI Agent (chat in) | talk to an LLM |
| B `stage_b_rag_chatbot.py` | Set (knowledge text) → Default Data Loader → Recursive Text Splitter → Embeddings OpenAI → Simple Vector Store → *Company Services Info* tool | RAG: split → embed → retrieve |
| C `stage_c_customer_details.py` | the agent asking for missing fields | structured customer intake |
| D `stage_d_agent_tools.py` | AI Agent + the 4 **Code Tools** | tools = deterministic functions |
| E `stage_e_excel_booking.py` | the Code Tools' persistent store | read/write the booking store |
| F `stage_f_observe_debug.py` | **Executions** tab (reasoning + tool calls per run) | observe & debug |

The n8n booking tools (`check_availability`, `check_duplicate_booking`, `save_booking`, `list_bookings`) implement the *same* Brightlane rules in JavaScript that `python/common.py` implements in Python.

---

## Quick start — Python path (with uv)

Requires Python ≥ 3.10 — `uv` fetches one automatically if needed.

```bash
# 0) install uv (https://docs.astral.sh/uv/getting-started/installation/)
curl -LsSf https://astral.sh/uv/install.sh | sh      # or: brew install uv / pipx install uv

# 1) install the locked dependencies (creates .venv)
uv sync

# 2) add your API keys — never commit .env
cp .env.example .env
#    then paste your keys into .env:
#      GROQ_API_KEY    -> https://console.groq.com/keys   (free, all stages)
#      OPENAI_API_KEY  -> https://platform.openai.com/api-keys  (Stage B only: embeddings)

# 3) run the stages in order
uv run python python/stage_a_chatbot.py
uv run python python/stage_b_rag_chatbot.py
uv run python python/stage_c_customer_details.py
uv run python python/stage_d_agent_tools.py
uv run python python/stage_e_excel_booking.py
uv run python python/stage_f_observe_debug.py

# reset the demo workbook any time (re-creates seed rows)
uv run python python/reset_workbook.py
```

Notes:

- `uv.lock` is committed, so `uv sync` gives everyone identical dependency versions.
- No `uv`? Plain pip works too: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- `data/bookings_python.xlsx` is gitignored; the first Stage E/F run (or `reset_workbook.py`) recreates it.
- The default Groq model is `openai/gpt-oss-120b` (set via `GROQ_MODEL` in `.env`). **Verify the model id in the Groq console before your session** — ids change occasionally.
- Stage F can stream traces to [LangSmith](https://smith.langchain.com) if you uncomment the `LANGSMITH_*` lines in `.env`. Optional.

## Quick start — n8n path

1. Open any reasonably current n8n (self-hosted is free; n8n Cloud works too).
2. Import the workflow: drag `n8n/customer_care_booking_assistant.json` onto the canvas
   (or *Workflows → Import from File*).
3. **Add credentials:** open the **OpenAI Chat Model** *and* **Embeddings OpenAI** sub-nodes and select/create one OpenAI credential.
   *(No keys are stored inside the JSON — you plug in your own.)*
4. Click **Chat** in the editor and talk to the assistant. Three seed bookings are preloaded.
5. To keep bookings **between chats**, publish/activate the workflow — the Code Tools persist via n8n *workflow static data*.
   In editor test runs the store starts fresh every run (docs: static data isn't available when testing), **which conveniently doubles as the demo reset**. For a guaranteed full reset, re-import the JSON.
6. Model defaults: chat `gpt-4o-mini`, embeddings `text-embedding-3-small` — swap on the respective sub-nodes (Gemini users: replace the two OpenAI sub-nodes with Gemini ones).
7. **Upgrade path:** the Code Tools are deliberately simple. For real persistence, replace them with
   [Data Table](https://docs.n8n.io/build/work-with-data/data-tables.md) or Google Sheets nodes — the tool *descriptions* stay the same, so the agent doesn't change.

---

## Test scenarios — run both stacks, compare the behaviour

Seed dates are always `today+2` and `today+3` (`reset_workbook.py` prints them; the n8n store seeds the same days). Say "tomorrow" or "next friday" in the n8n chat — the agent converts to ISO dates itself.

| # | Scenario | Say / run | Expected | Watch it in |
|---|---|---|---|---|
| 1 | **FAQ grounding** | *"How much is a plumbing visit, and is there a warranty?"* | `$99` and the 14-day workmanship warranty — answered from the knowledge document, not invention | Stage B · n8n: `Company Services Info` tool call |
| 2 | **Book a free slot** | *"Book Omar Diaz, phone 555-0134, Plumbing Visit on \<today+2\> at 09:00."* | Confirmed, returns **APT-0004** | Stage E · n8n: `Check Duplicate Booking` → `Check Availability` → `Save Booking` |
| 3 | **Slot conflict** | *"Book Maya Chen, Electrical Visit on \<Maya's date\> at 10:00."* | Refused — 10:00 that day is already taken by **APT-0001** | both |
| 4 | **Duplicate booking** | *"I'm Maya Chen again — book Home Deep Cleaning on \<Maya's date\>."* | Refused — duplicate rule (same customer + service + date), friendly explanation | both |
| 5 | **Closed on Sunday** | *"Can someone come next Sunday?"* | Refused — closed Sundays, offered Mon–Sat | both |
| 6 | **Off-grid slot/service** | *"Book 10:30" / "Book a Massage Spa"* | Refused with the valid options listed | both |
| 7 | **List** | *"Show me all bookings."* | The full table with refs | Stage E · n8n: `List Bookings` |
| 8 | **Observe & debug** | rerun the scenarios above | Python: `[agent → tool]` traces in Stage F (+ optional LangSmith) · n8n: **Executions** tab shows every reasoning step and tool call | Stage F · n8n Executions |

The conflict/duplicate demos are repeatable forever: reset the workbook (`reset_workbook.py`) or re-import the n8n workflow / test in the editor.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[setup] GROQ_API_KEY is missing` | `.env` missing or empty. It must sit in the repo root, named exactly `.env` (copy from `.env.example`). |
| `401` from a provider | Key pasted with quotes/spaces, or the wrong key. Re-paste it raw into `.env`. |
| Groq says the model doesn't exist | Model ids drift. Open the [Groq console](https://console.groq.com), copy a current chat model id into `GROQ_MODEL` in `.env`. |
| Stage B asks for `OPENAI_API_KEY` | Embeddings aren't offered by Groq; Stage B is the only stage that needs the OpenAI key (for `text-embedding-3-small`). |
| Excel looks odd / rows missing | `uv run python python/reset_workbook.py` regenerates the seed workbook. |
| `uv` not found | Install via the link above, or use the pip fallback from the quick start. |
| n8n: assistant answers but never uses tools | Check all five tool sub-nodes are wired to the AI Agent, and the tool **descriptions** (the LLM reads those to decide). |
| n8n: bookings vanish between tests | Static data only persists in *published* executions; editor test runs reset it by design. Activate the workflow to persist. |
| n8n: node-version warnings on import | Bring n8n up to date — the JSON targets the current stable node versions. |
| You committed your keys?! | Rotate the key immediately, then delete `.env` and re-add it (`.gitignore` already excludes it). |

---

## Why this repo is shaped like this

- **Same scenario, two implementations** — so you can discuss *where* each stack shines: n8n for fast assembly and visible execution history, Python for control, structure (Pydantic), and proper versioning of business logic.
- **Deterministic rules + an LLM** — the agent decides *what* to do; the tools decide *what is allowed*. That separation is the lesson.
- **No secrets in the repo** — `.env.example` is a template; `.gitignore` covers `.env` and demo data. Keep credentials off your slides too.

License: [MIT](LICENSE).
