"""Stage D — LangChain agent & tools (in-memory). (outline §3, Stage D)

What this stage demonstrates:
- plain Python functions -> LangChain tools with schemas (@tool + docstrings)
- the agent decides WHEN to call which tool (and we watch it choose)
- deterministic tools answer "real" questions: availability & duplicates
- returned results feed back into the model's answer

Run:  python python/stage_d_agent_tools.py     (type 'quit' to exit)
"""
from datetime import date, timedelta

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from common import PLAIN_TEXT_RULE, SERVICES, SLOT_START_TIMES, get_llm

# In-memory mock of "what is already booked" (Stage E swaps this for Excel).
_TODAY = date.today()
_SEED_DATE = (_TODAY + timedelta(days=3)).isoformat()  # handy relative date for demos
_PREBOOKED = [
    {"customer": "Maya Chen", "service": "Admission Counselling", "date": _SEED_DATE, "time": "10:00"},
    {"customer": "Dmitri Volkov", "service": "Fee Payment Assistance", "date": _SEED_DATE, "time": "14:00"},
]


@tool
def check_availability(check_date: str) -> str:
    """Return which hourly start times (09:00-16:00) are still free on a given date.
    Use a specific date like 2026-11-20. Sundays are closed."""
    d = date.fromisoformat(check_date)  # schema, not hope: the caller must send ISO
    if d.weekday() == 6:
        return f"{check_date} is a CLOSED day (Sundays only)."
    booked = {b["time"] for b in _PREBOOKED if b["date"] == check_date}
    free = [t for t in SLOT_START_TIMES if t not in booked]
    return (
        f"{check_date} availability -> booked: {booked or 'none'} | "
        f"free start times: {', '.join(free) or 'none (fully booked)'}"
    )


@tool
def check_duplicate_booking(customer_name: str, booking_date: str, service: str) -> str:
    """Find whether this exact customer already has a booking with the same
    service on the same date (case-insensitive). Duplicate rule of outline §4."""
    matches = [
        b for b in _PREBOOKED
        if b["customer"].casefold() == customer_name.casefold()
        and b["date"] == booking_date
        and b["service"].casefold() == service.casefold()
    ]
    if not matches:
        return f"No duplicate found for {customer_name} ({service} on {booking_date})."
    b = matches[0]
    return (
        f"DUPLICATE for {customer_name}: {b['service']} already booked on {b['date']} "
        f"at {b['time']}. Ask whether they want to change it instead of rebooking."
    )


BOOKING_TOOLS = [check_availability, check_duplicate_booking]

AGENT_SYSTEM = (
    "You are the Brainware University help-desk/booking agent.\n"
    f"Services: {', '.join(SERVICES)}. Today is {_TODAY.isoformat()}.\n"
    "Before recommending any booking decision, always verify with the tools:\n"
    "  - availability of date/time (check_availability)\n"
    "  - repeat bookings of the same customer+date+service (check_duplicate_booking)\n"
    "Never invent slot availability or prices; rely on tool results and say when data is missing."
    + PLAIN_TEXT_RULE
)


def build_agent():
    """LangGraph's ReAct agent = model + tools + system prompt (outline §3-D)."""
    return create_react_agent(get_llm(), BOOKING_TOOLS, prompt=AGENT_SYSTEM)


def print_trace(final_state: dict) -> None:
    """Show the full thought -> tool-call -> tool-result -> answer chain."""
    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  [agent -> tool] {tc['name']}({tc['args']})")
        elif msg.__class__.__name__ == "ToolMessage":
            print(f"  [tool -> agent] {msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            print(f"\nAssistant: {msg.content}\n")


def main() -> None:
    agent = build_agent()

    print("Behold the agent's tool selection live. Pre-seeded demo booking:")
    for b in _PREBOOKED:
        print(f"  {b['customer']} - {b['service']} - {b['date']} {b['time']}")
    print("Try asking: 'Is Maya Chen already booked for admission counselling on', or")
    print("            'Which times are free', or 'Can Dmitri book anything at 14:00?'\n")
    usage = check_availability.invoke({"check_date": _SEED_DATE})  # direct tool call, no agent needed
    print(f"Direct tool call check_availability('{_SEED_DATE}') -> {usage}\n")

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

        messages = final_state["messages"]  # keep tool traffic in history
        print_trace(final_state)

    print("(Stage D done. Next: Stage E swaps the mock for a real Excel workbook.)")


if __name__ == "__main__":
    main()
