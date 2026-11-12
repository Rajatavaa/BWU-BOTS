"""Stage C — Customer details & state. (outline §3, Stage C)

What this stage demonstrates:
- structured extraction: chat history -> a Pydantic schema (CustomerDetails)
- schema validation, missing-field checks and normalisation (date/time!)
- separation of "user intent" from "validated data": only normalized,
  validated values survive, so Stage E can hand them straight to tools.

Run:  python python/stage_c_customer_details.py     (type 'quit' to exit)
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from common import SERVICES, get_llm, normalize_time, parse_date, validate_slot

CUSTOMER_SYSTEM = (
    "You are the help-desk assistant of Brainware University.\n"
    "Collect, in a natural chat flow, the customer's: full name, phone, service, date, time.\n"
    f"Our services: {', '.join(SERVICES)}.\n"
    "Ask for at most one missing item per reply and confirm what you captured."
)


class CustomerDetails(BaseModel):
    """The structured, machine-checkable version of what the customer said."""
    full_name: str = Field(default="", description="Customer's full name; empty string if not known yet.")
    phone: str = Field(default="", description="Phone number as the customer typed it; empty string if unknown.")
    service: str = Field(default="", description="One of the Brainware help-desk service names; empty string if unknown.")
    date: str = Field(default="", description="Requested date, as the customer phrased it; empty string if unknown.")
    time: str = Field(default="", description="Requested time, as the customer phrased it; empty string if unknown.")


REQUIRED_FIELDS = ("full_name", "phone", "service", "date", "time")


def missing_fields(details: CustomerDetails) -> list[str]:
    return [name for name in REQUIRED_FIELDS if "" == getattr(details, name)]


def diagnose(details: CustomerDetails) -> list[str]:
    """Deterministic validation & normalisation on top of the raw model output."""
    problems: list[str] = []

    date_iso = parse_date(details.date) if details.date else None
    if details.date and date_iso is None:
        problems.append(f"Date '{details.date}' could not be understood (try 2026-11-20 or 'next friday').")

    try:
        time_hhmm = normalize_time(details.time) if details.time else None
    except ValueError as exc:
        problems.append(str(exc))
        time_hhmm = None

    if date_iso and time_hhmm:
        problems.extend(validate_slot(date_iso, time_hhmm))

    if details.service and details.service.casefold() not in {s.casefold() for s in SERVICES}:
        problems.append(f"Service '{details.service}' is not one of our offers: {SERVICES}")

    return problems


def main() -> None:
    llm = get_llm()
    extractor = llm.with_structured_output(CustomerDetails)  # model -> schema (function calling)

    print("Stage C demo. Drip-feed details or give them all at once.")
    print("Examples: 'Maya Chen, 555-0143'  |  'Admission counselling next friday at 11am'\n")

    history: list = [SystemMessage(content=CUSTOMER_SYSTEM)]  # conversation state
    details = CustomerDetails()  # validated data state (kept separate on purpose)

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            break

        history.append(HumanMessage(content=user))
        try:
            details = extractor.invoke(history)  # whole history -> whole schema
        except Exception as exc:
            print(f"  Model error: {exc}")
            history.pop()
            continue
        history.append(AIMessage(content="Noted."))

        print(f"  captured: {details.model_dump_json()}")
        problems = diagnose(details)
        missing = missing_fields(details)
        if problems:
            print(f"  validation problems: {problems}")
        if missing:
            print(f"  still missing: {missing}")
        if not problems and not missing:
            print(
                "\n  Ready-for-tools payload (validated & normalized): "
                f"name={details.full_name} phone={details.phone} "
                f"service={details.service} date={parse_date(details.date)} "
                f"time={normalize_time(details.time)}"
            )
            print("    (Stage E will pass exactly these values into booking tools.)")
        print()

    print("(Stage C done. Next: Stage D exposes our business checks as agent tools.)")


if __name__ == "__main__":
    main()
