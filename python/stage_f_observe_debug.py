"""Stage F — Observe & debug: scripted scenarios. (outline §3, Stage F + §5 table)

Runs the four side-by-side demo scenarios against the Stage E agent and prints
the whole reasoning trace for each: chosen tools, tool inputs/outputs,
final answers and token usage. Compare the exact same prompts in the n8n
workflow (n8n/customer_care_booking_assistant.json).

Run:  python python/reset_workbook.py && python python/stage_f_observe_debug.py

Optional: set LANGSMITH_TRACING=true + LANGSMITH_API_KEY in .env for hosted traces.
"""
import os

from langchain_core.messages import AIMessage, HumanMessage

import common
from stage_e_excel_booking import build_agent, print_trace

SCENARIO_LABELS = {
    "services":   "Ask a company question (grounded by the FAQ doc)",
    "booking":    "Book a valid, free slot",
    "duplicate":  "Retry the SAME customer/date/service (must be rejected)",
    "conflict":   "Request an occupied time slot (must get alternatives)",
}


def build_scenarios() -> list[dict]:
    """Scenarios read their dates from the seeded workbook -> demo always reproducible."""
    rows = {str(r["customer"]): r for r in common.load_workbook_rows()}
    maya = rows["Maya Chen"]          # seeded: Home Deep Cleaning
    maya_date = str(maya["date"])     # her booked date (duplicate scenario)
    occupied = next(r for r in rows.values() if str(r["time"]) == "10:00")  # 10:00 is taken
    return [
        {
            "key": "services",
            "prompt": "What services can I book, and how much does deep cleaning cost?",
        },
        {
            "key": "booking",
            "prompt": (
                "I'm Nadia Fox, phone 555-0119. Please book a Home Deep Cleaning on "
                f"{maya_date} at 15:00."
            ),
        },
        {
            "key": "duplicate",
            "prompt": (
                "Hi, Maya Chen here, phone 555-0143. I want to book Home Deep Cleaning again on "
                f"{maya_date}, 15:00."
            ),
        },
        {
            "key": "conflict",
            "prompt": (
                "This is Priya Nair, 555-0188. Book an Appliance Repair Visit on "
                f"{str(occupied['date'])} at 10:00."
            ),
        },
    ]


def temperature_note() -> str:
    return f"Model: {common.get_groq_model()} | temperature=.2 | LangSmith tracing: " + (
        "ON (see prints in your langsmith project)" if os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1") else "off (set LANGSMITH_TRACING=true to enable)"
    )


def run_one(label: str, prompt: str) -> dict:
    print("\n" + "=" * 74)
    print(f"SCENARIO: {label}")
    print(f"You: {prompt}")
    agent = build_agent()  # fresh agent per scenario: no cross-run memory
    final_state = agent.invoke({"messages": [HumanMessage(content=prompt)]})
    print_trace(final_state)

    last = final_state["messages"][-1]
    if isinstance(last, AIMessage):
        usage = getattr(last, "usage_metadata", None)
        if usage:
            print(
                f"  token usage: {usage['input_tokens']} in / {usage['output_tokens']} out (whole run)"
            )
        return {"label": label, "answer": last.content, "usage": usage}
    return {"label": label, "answer": last.content}


def main() -> None:
    common.ensure_workbook()
    print("Stage F - scripted debugging pass (reset the workbook first for clean runs)")
    print(temperature_note())
    print("Compare 1:1 with the n8n version: n8n/customer_care_booking_assistant.json\n")

    for scenario in build_scenarios():
        run_one(SCENARIO_LABELS[scenario["key"]], scenario["prompt"])
        print(f"  workbook rows now: {len(common.load_workbook_rows())}")

    print("\nAll scenarios finished. What to check in class:")
    print("  - the [agent -> tool] lines: WHO decided what (model) vs WHAT is true (tools)")
    print("  - duplicate/conflict scenarios: deterministic rejections, not hallucinated ones")
    print("  - token usage & rate limits: why the demo model is configured with low temperature")
    print("  - retry the same prompts in the n8n workflow to compare behaviour")


if __name__ == "__main__":
    main()
