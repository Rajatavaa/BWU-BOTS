"""Stage E — Excel appointment booking agent. (outline §3, Stage E)

Combines Stages C + D against a real Excel workbook (openpyxl):
- tools now READ/WRITE data/bookings_python.xlsx (Excel persistence)
- save_booking only saves after deterministic checks, returns a Booking ref
- assistant answers FAQ questions grounded in the same document as Stage B

Run:  python python/reset_workbook.py   (once, to create the workbook)
      python python/stage_e_excel_booking.py     (type 'quit' to exit)
"""
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

import common
from common import (
    COMPANY_DOCUMENT,
    SERVICES,
    WORKBOOK_PATH,
    get_llm,
    normalize_time,
    parse_date,
    validate_slot,
)

_TODAY = date.today().isoformat()


@tool
def check_availability(check_date: str) -> str:
    """Check which start times (09:00-16:00 hourly) free/occupied on a date (YYYY-MM-DD).
    Sundays are closed. Use it BEFORE answering anything about availability."""
    try:
        date_iso = parse_date(check_date) or check_date
        date.fromisoformat(date_iso)
    except (ValueError, TypeError):
        return f"Unparseable date {check_date!r}. Ask the customer to clarify (e.g. 2026-11-20)."

    rows = common.load_workbook_rows()
    booked = sorted(r["time"] for r in rows if r["status"] == "Confirmed" and str(r["date"]) == date_iso)
    free = [t for t in common.SLOT_START_TIMES if t not in set(booked)]
    return (
        f"{date_iso} -> booked slots: {booked or 'none'} | free start times: "
        f"{', '.join(free) or 'none (fully booked)'}"
    )


@tool
def check_duplicate_booking(customer_name: str, booking_date: str, service: str) -> str:
    """Check whether the customer already has a same-service booking on the same date.
    Duplicate rule = customer + date + service (case-insensitive)."""
    date_iso = parse_date(booking_date) or booking_date
    match = next(
        (
            r for r in common.load_workbook_rows()
            if common.matches(r, customer=customer_name, service=service, date_iso=date_iso)
        ),
        None,
    )
    if not match:
        return f"No duplicate for {customer_name} - {service} on {date_iso}. Safe to book."
    return (
        f"Existing booking {match['Booking Ref']}: {match['Service']} on {match['Date']} at "
        f"{match['Time']} (customer {customer_name}). Ask if they want to change or cancel it; "
        "do NOT create a second booking for the same thing."
    )


@tool
def save_booking(customer_name: str, phone: str, service: str, booking_date: str, time: str) -> str:
    """Save a CONFIRMED booking row to the Excel file after all deterministic checks.
    Returns the booking reference (APT-XXXX). Never quote a ref before this succeeds."""
    # 1. normalize
    date_iso = parse_date(booking_date)
    try:
        time_hhmm = normalize_time(time)
    except ValueError as exc:
        return f"Invalid time: {exc}"
    if date_iso is None:
        return f"Unparseable date {booking_date!r}; ask the customer to clarify (e.g. 2026-11-20)."
    if service not in SERVICES:
        return f"Service '{service}' is not offered. Offer one of: {', '.join(SERVICES)}"

    # 2. deterministic business checks - keep rules OUT of the LLM (§4)
    problems = validate_slot(date_iso, time_hhmm)
    rows = common.load_workbook_rows()
    dup = next((r for r in rows if common.matches(r, customer=customer_name, service=service, date_iso=date_iso)), None)
    if dup:
        problems.append(f"Duplicate booking {dup['Booking Ref']} already holds this slot for them ({dup['Time']}).")
    if common.slot_conflict(rows, date_iso, time_hhmm):
        problems.append("That time slot is already taken - suggest a different time.")
    if problems:
        return "NOT SAVED -> " + " | ".join(problems)

    # 3. write + read-back verify (§4: "verify before saving, then re-check results")
    ref = common.next_ref()
    row = {
        "ref": ref, "customer": customer_name, "phone": phone, "service": service,
        "date": date_iso, "time": time_hhmm, "status": "Confirmed", "created": _TODAY,
    }
    common.append_rows(rows=[row])
    saved = [r for r in common.load_workbook_rows() if str(r["ref"]) == ref]
    if not saved:
        return f"Save of {ref} could NOT be verified in the workbook - tell customer to try again."
    s = saved[0]
    return (
        f"BOOKED {ref}: {s['service']} with {s['customer']} on {s['date']} at {s['time']} "
        f"(saved and verified in data/bookings_python.xlsx)."
    )


BOOKING_TOOLS = [check_availability, check_duplicate_booking, save_booking]

_AGENT_SYSTEM = (
    "You are the customer care & appointment booking assistant of Brightlane Home Services.\n"
    f"Today = {_TODAY}. Working hours: Mon-Sat, hourly 09:00-16:00 starts, Sundays closed.\n"
    f"Pick a service strictly from: {', '.join(SERVICES)}.\n"
    "\nYou are the booking assistant. Flow to CONFIRM a booking:\n"
    "  1. collect full name, phone, service, date, time by chatting with the customer\n"
    "  2. check_availability(date) to show/prove free slots on that date\n"
    "  3. check_duplicate_booking(name, date, service) - customer repeat-bookings rule\n"
    "  4. save_booking(...) ONLY if both checks passed, then reply with the returned APT ref\n"
    "If the requested time is occupied, offer the freshest free list from the tool - "
    "never promise availability the tools did not report.\n"
    "Never invent prices, policies or slots; use the FAQ below when answering company questions.\n"
    "\n--- COMPANY FAQ (used for non-booking questions) ---\n"
)

AGENT_SYSTEM_WITH_FAQ = _AGENT_SYSTEM + COMPANY_DOCUMENT.read_text(encoding="utf-8")


def build_agent():
    """Same recipe as Stage D, plus the save_booking tool (LangGraph ReAct agent)."""
    return create_react_agent(get_llm(), BOOKING_TOOLS, prompt=AGENT_SYSTEM_WITH_FAQ)


def print_trace(final_state: dict) -> None:
    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  [agent -> tool] {tc['name']}({tc['args']})")
        elif msg.__class__.__name__ == "ToolMessage":
            print(f"  [tool -> agent] {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            print(f"\nAssistant: {msg.content}\n")


def main() -> None:
    common.ensure_workbook()  # creates data/bookings_python.xlsx if needed
    print(f"Booking store: {WORKBOOK_PATH}  (reset any time: python python/reset_workbook.py)")
    print("Try a full booking: 'Daniel Reed, 555-0121' then ask for an appointment.")
    print("Watch [agent -> tool] lines: this is Stage D, now with real Excel persistence.\n")

    agent = build_agent()
    messages: list = []
    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            break

        messages.append(HumanMessage(content=user))
        try:
            final_state = agent.invoke({"messages": messages})
        except Exception as exc:
            print(f"  Agent error: {exc}")
            messages.pop()
            continue

        messages = final_state["messages"]
        print_trace(final_state)

    print("(Stage E done. Next: Stage F runs the scripted comparison scenarios.)")


if __name__ == "__main__":
    main()
