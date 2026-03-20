"""
Multi-Agent Travel Booking using Agno Team (Sequential Mode)
Matches ADK SequentialAgent pattern for cleaner traces.
"""

import time
from agno.agent import Agent
from agno.models.google import Gemini
from agno.team import Team
from agno.team.mode import TeamMode
from agno.tools import tool

# Monocle Setup
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="agno-multi-agent-travel",
    monocle_exporters_list="okahu",
)
print("Monocle telemetry initialized")


# Simple Tools (matching ADK pattern)
@tool
def book_flight(from_airport: str, to_airport: str) -> dict:
    """Books a flight from one airport to another."""
    return {
        "status": "success",
        "message": f"Flight booked from {from_airport} to {to_airport}."
    }


@tool
def book_hotel(hotel_name: str, city: str) -> dict:
    """Books a hotel for a stay."""
    return {
        "status": "success",
        "message": f"Successfully booked a stay at {hotel_name} in {city}."
    }


# Sub-Agents
flight_agent = Agent(
    name="Flight Agent",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[book_flight],
    role="Book flights based on user queries",
    instructions=[
        "You are a helpful agent who assists users in booking flights.",
        "Extract flight details and book using book_flight tool.",
    ],
)

hotel_agent = Agent(
    name="Hotel Agent",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[book_hotel],
    role="Book hotels based on user queries",
    instructions=[
        "You are a helpful agent who assists users in booking hotels.",
        "Default to Marriott if no hotel specified.",
        "Use the book_hotel tool with hotel_name and city.",
    ],
)

trip_summary_agent = Agent(
    name="Trip Summary Agent",
    model=Gemini(id="gemini-2.0-flash"),
    role="Summarize travel bookings",
    instructions=[
        "Summarize the travel details from flight and hotel bookings.",
        "Be concise and provide a single sentence summary."
    ],
)

# Team with sequential task mode (like ADK SequentialAgent)
travel_team = Team(
    name="Travel Team",
    mode=TeamMode.coordinate,
    model=Gemini(id="gemini-2.0-flash"),
    members=[flight_agent, hotel_agent, trip_summary_agent],
    instructions=[
        "Execute agents in sequence: flight booking, then hotel booking, then summary.",
        "Pass the user request to each agent in order.",
    ],
    share_member_interactions=True,
    markdown=True,
)

if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Agent Travel (Agno Team + Gemini + Monocle)")
    print("=" * 60)

    query = "Book a flight from SJC to SEA and a hotel in Seattle."
    print(f"Query: {query}\n")

    result = travel_team.run(query, stream=False)
    print(f"\nResult: {result.content if hasattr(result, 'content') else result}")

    print("\nWaiting for traces...")
    time.sleep(5)
    print("Done! Check Okahu.")
