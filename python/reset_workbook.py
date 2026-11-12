"""Reset the demo booking workbook (outline, Implementation notes: "separately
reset demo workbooks").

Run:  python python/reset_workbook.py
"""
from common import WORKBOOK_PATH, ensure_workbook, load_workbook_rows, seed_demo_bookings


def main() -> None:
    ensure_workbook(reset=True)
    rows = load_workbook_rows(WORKBOOK_PATH)
    print(f"Recreated {WORKBOOK_PATH} with {len(rows)} seed rows:\n")
    for r in rows:
        print(f"  {r['ref']} | {r['customer']} | {r['service']} | {r['date']} at {r['time']}")
    maya = next(r for r in rows if r["customer"] == "Maya Chen")
    print(
        "\nHandy demo prompts (dates are relative to today):\n"
        f"  - Slot-conflict test -> {maya['date']} 10:00 is taken by Maya Chen.\n"
        "  - Duplicate test    -> ask Maya Chen to book Admission Counselling on her existing date again.\n"
        "  Then run: python python/stage_e_excel_booking.py\n"
    )
    # keep the seed function referenced for linters
    _ = seed_demo_bookings


if __name__ == "__main__":
    main()
