import os
import json
import requests
from datetime import datetime, timezone, timedelta

GHL_TOKEN = os.environ["GHL_TOKEN"]
LOCATION_ID = os.environ["GHL_LOCATION_ID"]

BASE_URL = "https://services.leadconnectorhq.com"
HEADERS = {
    "Authorization": f"Bearer {GHL_TOKEN}",
    "Version": "2021-04-15",
    "Content-Type": "application/json"
}

CALENDAR_IDS = [
    "6KiVbrUzAImXZ7bP1GyJ",  # Design Consultation Austin
    "136oxD4jIEtZKCitj3zp",  # Design Consultation Houston
    "ZSdptFjT3B4rUmWfFh7K",  # Design Consultation San Antonio
]

HUMAN_SOURCES = {"mobile_app", "opportunity_page", "contact_page"}
AUTO_SOURCES = {"conversations_ai", "third_party", "workflow", "api"}

SOURCE_LABELS = {
    "mobile_app": "Mobile app",
    "opportunity_page": "CRM page",
    "contact_page": "CRM page",
    "booking_widget": "Booking widget",
    "conversations_ai": "Conversations AI",
    "third_party": "Third party",
    "workflow": "Workflow",
    "api": "API",
}

def classify(appt):
    src = (appt.get("createdBy") or {}).get("source", "unknown")
    uid = (appt.get("createdBy") or {}).get("userId")
    if src in HUMAN_SOURCES or (uid and src not in AUTO_SOURCES and src != "booking_widget"):
        return "human"
    if src == "booking_widget":
        return "self"
    if src in AUTO_SOURCES:
        return "auto"
    return "other"

def fetch_appointments():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    all_appointments = []
    seen = set()

    for cal_id in CALENDAR_IDS:
        try:
            r = requests.get(
                f"{BASE_URL}/calendars/events",
                headers=HEADERS,
                params={
                    "locationId": LOCATION_ID,
                    "calendarId": cal_id,
                    "startTime": start_ms,
                    "endTime": end_ms,
                }
            )
            r.raise_for_status()
            events = r.json().get("events", [])
            for ev in events:
                if ev["id"] not in seen:
                    seen.add(ev["id"])
                    all_appointments.append(ev)
        except Exception as e:
            print(f"Error fetching calendar {cal_id}: {e}")

    return all_appointments, start.isoformat(), now.isoformat()

def build_output(appointments, start_date, end_date):
    total = len(appointments)
    counts = {"human": 0, "auto": 0, "self": 0, "other": 0}
    source_counts = {}
    rows = []

    for appt in appointments:
        appt_type = classify(appt)
        counts[appt_type] += 1

        src = (appt.get("createdBy") or {}).get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

        rows.append({
            "id": appt.get("id"),
            "title": appt.get("title", ""),
            "startTime": appt.get("startTime", ""),
            "calendarId": appt.get("calendarId", ""),
            "status": appt.get("appointmentStatus", ""),
            "type": appt_type,
            "source": src,
            "sourceLabel": SOURCE_LABELS.get(src, src),
            "userId": (appt.get("createdBy") or {}).get("userId"),
        })

    rows.sort(key=lambda x: x["startTime"], reverse=True)

    return {
        "meta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "startDate": start_date,
            "endDate": end_date,
            "locationId": LOCATION_ID,
        },
        "summary": {
            "total": total,
            "human": counts["human"],
            "auto": counts["auto"],
            "selfBooked": counts["self"],
            "other": counts["other"],
            "humanPct": round(counts["human"] / total * 100) if total else 0,
            "autoPct": round(counts["auto"] / total * 100) if total else 0,
            "notHumanPct": round((total - counts["human"]) / total * 100) if total else 0,
        },
        "sourceCounts": source_counts,
        "appointments": rows,
    }

def main():
    print("Fetching appointments from GHL...")
    appointments, start_date, end_date = fetch_appointments()
    print(f"Fetched {len(appointments)} appointments")

    output = build_output(appointments, start_date, end_date)

    with open("data.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Written data.json — {output['summary']['total']} appointments, "
          f"{output['summary']['human']} human, "
          f"{output['summary']['auto']} auto")

if __name__ == "__main__":
    main()
