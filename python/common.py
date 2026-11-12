"""Shared helpers for the Python path of the workshop.

Centralises the "boring but important" parts so the five stage scripts
(Stages A-E) can stay small and readable:

- .env loading and API-key checks (Groq chat model, OpenAI embeddings)
- the help desk's business rules (appointment purposes, slots, validation)
- Excel read/write helpers for data/bookings_appointments.xlsx (openpyxl)
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Load .env from the repo root no matter where the script is started from.
load_dotenv(find_dotenv(usecwd=False), override=False)

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
COMPANY_DOCUMENT = DATA_DIR / "brainware.md"
WORKBOOK_PATH = DATA_DIR / "bookings_python.xlsx"

# --- Model configuration (all keys stay in .env, never printed) ---
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"  # verify in the Groq console before the session

BOOKINGS_HEADERS = ["Booking Ref", "Customer Name", "Phone", "Service", "Date", "Time", "Status", "Created"]

SLOT_START_TIMES = [f"{h:02d}:00" for h in range(9, 17)]  # hourly starts 09:00..16:00

SERVICES = [
    "Admission Counselling",
    "Campus Tour",
    "Hostel Enquiry",
    "Exam Support",
    "Scholarship Guidance",
    "Fee Payment Assistance",
]

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def _instruct(key: str, url: str) -> str:
    return (
        f"\n[setup] {key} is missing.\n"
        "  1. Copy .env.example to .env  (cp .env.example .env)\n"
        f"  2. Paste your key from {url} next to {key}=\n"
        "  3. Run this script again.  (Never commit .env — it is gitignored.)\n"
    )


def require_groq_key() -> str:
    """Return GROQ_API_KEY or exit with a friendly setup hint."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key or "REPLACE" in key.upper():
        sys.stderr.write(_instruct("GROQ_API_KEY", "https://console.groq.com/keys"))
        sys.exit(1)
    return key


def require_openai_key() -> str:
    """Stage B only: embeddings need a separate provider (Groq has none)."""
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or "REPLACE" in key.upper():
        sys.stderr.write(_instruct("OPENAI_API_KEY", "https://platform.openai.com/api-keys"))
        sys.exit(1)
    return key


def get_groq_model() -> str:
    return os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip()


# Appended to every chat system prompt: answers are read in a terminal, where
# Markdown tables / **bold** / <links> show up as raw symbols.
PLAIN_TEXT_RULE = (
    "\nFORMAT: reply in plain text for a terminal. No Markdown: no tables, no ** or # symbols, "
    "no <angle-bracket> links. Use short sentences, or simple '- ' bullet lines with one idea each. "
    "Keep the answer under about 120 words and finish with one short follow-up question."
)


def get_llm(temperature: float = 0.2):
    """Groq chat model via LangChain. Note how explicit the auth step is — and
    that we never echo the key back."""
    from langchain_groq import ChatGroq

    model = get_groq_model()
    extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}  # gpt-oss thinks a lot by default = slow
    return ChatGroq(model=model, api_key=require_groq_key(), temperature=temperature, **extra)


# --- Deterministic "business rules" (the non-LLM side of the assistant) ---
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
    "%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y",
    "%d %B", "%B %d", "%d %b", "%b %d",
)

_WEEKDAY_RE = re.compile(r"\b(next\s+)?(mon|tues|wednes|thurs|fri|satur|sun|mon|tues|weds|thur|thurs)[a-z]*", re.I)
_IN_DAYS_RE = re.compile(r"\bin\s+(\d+)\s+days?\b", re.I)
_ORDINAL_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.I)


def parse_date(text: str, today: date | None = None) -> str | None:
    """Normalise human date phrases to YYYY-MM-DD. Returns None when unreadable.

    Handles: YYYY-MM-DD, 20/11/2026, November 20, 20 Nov, tomorrow,
    next friday, friday, in 3 days.
    """
    today = today or date.today()
    t = text.strip().lower()
    t = _ORDINAL_RE.sub(r"\1", t).replace(",", "").strip()

    if t in {"today"}:
        return today.isoformat()
    if t in {"tomorrow"}:
        return (today + timedelta(days=1)).isoformat()
    if t in {"day after tomorrow"}:
        return (today + timedelta(days=2)).isoformat()
    m = _IN_DAYS_RE.search(t)
    if m:
        return (today + timedelta(days=int(m.group(1)))).isoformat()

    m = _WEEKDAY_RE.search(t)
    if m:
        prefix = m.group(2)[:3]  # regex groups always match a 3-letter entry of WEEKDAYS
        target = WEEKDAYS[prefix]
        for add in range(0, 14):
            cand = today + timedelta(days=add)
            if cand.weekday() != target:
                continue
            if m.group(1):  # "next X" -> strictly NEXT week's X
                cand = cand + timedelta(days=7)
            return max(cand, today).isoformat()

    cleaned = re.sub(r"\s+at\b.*$", "", t).strip()
    yearless = cleaned and not re.search(r"\d{4}", cleaned)
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if yearless and ("%" + "Y") not in fmt:  # formats without a year: assume current year
            dt = dt.replace(year=today.year)
            if dt.date() < today:
                dt = dt.replace(year=today.year + 1)  # no year given -> take the future date
        return dt.date().isoformat()
    return None


_TIME_RE = re.compile(r"^(\d{1,2})(?::?(\d{2}))?\s*(am|pm|h)?$", re.I)


def normalize_time(text: str) -> str:
    """Normalise human times to HH:MM (24h) or raise ValueError.

    Handles: 14:30, 2:30 pm, 10 am, 10pm, noon.
    """
    t = text.strip().lower().replace(".", ":").replace("a.m", "am").replace("p.m", "pm")
    if t in {"noon", "midday", "12pm"}:
        return "12:00"
    m = _TIME_RE.match(t)
    if not m:
        raise ValueError(f"Unrecognised time: {text!r}")
    hour, minute, suffix = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if minute >= 60 or hour > 23:
        raise ValueError(f"Time out of range: {text!r}")
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def validate_slot(date_iso: str, time_hhmm: str) -> list[str]:
    """Business-rule check for one deterministic slot. Returns human-readable errors."""
    problems: list[str] = []
    d = date.fromisoformat(date_iso)
    if d < date.today():
        problems.append(f"{date_iso} is in the past.")
    if d.weekday() == 6:
        problems.append("We are closed on Sundays — pick Monday to Saturday.")
    if time_hhmm not in SLOT_START_TIMES:
        problems.append(
            "Start times run hourly 09:00-16:00 (" + ", ".join(SLOT_START_TIMES) + "); "
            f"'{time_hhmm}' is not a bookable start time."
        )
    return problems


# --- Excel (openpyxl) helpers: the demo booking store ---
def ensure_workbook(path: Path | None = None, reset: bool = False) -> Path:
    """Make sure the bookings workbook exists (created with demo seed rows if missing)."""
    from openpyxl import Workbook, load_workbook

    path = Path(path or WORKBOOK_PATH)

    if reset and path.exists():
        path.unlink()

    if not path.exists():
        wb = Workbook()
        ws = wb.active
        ws.title = "Appointments"
        ws.append(BOOKINGS_HEADERS)
        for row in seed_demo_bookings().values():
            ws.append([row["ref"], row["customer"], row["phone"], row["service"],
                       row["date"], row["time"], row["status"], row["created"]])
        wb.save(path)
        return path

    load_workbook(path).close()  # cheap sanity check
    return path


def seed_demo_bookings() -> dict[str, dict]:
    """Deterministic demo data: dates relative to today so the demo always works.
    Slot conflicts and the repeat-booking scenario are re-testable after a reset."""
    d1 = (date.today() + timedelta(days=3)).isoformat()
    d2 = (date.today() + timedelta(days=2)).isoformat()
    return {
        1: {"ref": "APT-0001", "customer": "Maya Chen", "phone": "555-0143",
            "service": "Admission Counselling", "date": d1, "time": "10:00",
            "status": "Confirmed", "created": datetime.now().isoformat(timespec="minutes")},
        2: {"ref": "APT-0002", "customer": "Dmitri Volkov", "phone": "555-0177",
            "service": "Fee Payment Assistance", "date": d2, "time": "14:00",
            "status": "Confirmed", "created": datetime.now().isoformat(timespec="minutes")},
        3: {"ref": "APT-0003", "customer": "Elena Petrova", "phone": "555-0164",
            "service": "Hostel Enquiry", "date": d2, "time": "16:00",
            "status": "Confirmed", "created": datetime.now().isoformat(timespec="minutes")},
    }


def load_workbook_rows(path: Path = WORKBOOK_PATH):
    """Read the Appointments sheet as normalized lowercase-key dicts.
    Keys: ref, customer, phone, service, date, time, status, created."""
    from openpyxl import load_workbook

    ensure_workbook(path)
    wb = load_workbook(path)
    ws = wb["Appointments"]
    headers = [c.value for c in ws[1]]
    _MAP = {"Booking Ref": "ref", "Customer Name": "customer", "Phone": "phone",
            "Service": "service", "Date": "date", "Time": "time",
            "Status": "status", "Created": "created"}
    rows = []
    for r in ws.iter_rows(min_row=2):
        raw = {(_MAP.get(str(header), str(header))): value
               for header, value in zip(headers, (c.value for c in r))}
        if any(raw.get(k) not in (None, "") for k in ("ref", "customer", "service")):
            rows.append(raw)  # skip blank spreadsheet rows
    wb.close()
    return rows


def append_rows(rows: list[dict], path: Path = WORKBOOK_PATH) -> None:
    from openpyxl import load_workbook

    wb = load_workbook(path)
    ws = wb["Appointments"]
    for row in rows:
        ws.append([row["ref"], row["customer"], row["phone"], row["service"],
                   row["date"], row["time"], row["status"], row["created"]])
    wb.save(path)
    wb.close()


def next_ref(path: Path = WORKBOOK_PATH) -> str:
    """Sequential booking reference from the current number of rows."""
    highest = 0
    for r in load_workbook_rows(path):
        value = str(r["ref"] or "")
        if value.startswith("APT-"):
            try:
                highest = max(highest, int(value.split("-", 1)[1]))
            except ValueError:
                continue
    return f"APT-{highest + 1:04d}"


def matches(row: dict, *, customer: str, service: str, date_iso: str) -> bool:
    """Duplicate rule: same customer + date + service (case-insensitive), per outline §2/§4."""
    return (
        str(row["status"]).lower() == "confirmed"
        and str(row["customer"]).casefold() == customer.casefold()
        and str(row["service"]).casefold() == service.casefold()
        and str(row["date"]) == date_iso
    )


def slot_conflict(rows: list[dict], date_iso: str, time_hhmm: str) -> bool:
    """Slot rule: any confirmed booking at the same date+time occupies the 60-min slot."""
    return any(
        str(r["status"]).lower() == "confirmed" and str(r["date"]) == date_iso and str(r["time"]) == time_hhmm
        for r in rows
    )
