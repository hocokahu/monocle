"""
Multi-Agent Travel Booking: Travel Agent -> Flight Agent -> Hotel Agent
With Monocle instrumentation for observability.
"""

import time
from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools import tool

# Monocle Setup
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry

setup_monocle_telemetry(
    workflow_name="agno-multi-agent-travel",
    monocle_exporters_list="okahu",
)
print("Monocle telemetry initialized")

# Mock Tools
@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search flights between cities."""
    return f"Flights from {origin} to {destination} on {date}: UA123 ($350), DL789 ($280)"

@tool
def book_flight(flight: str, passenger: str) -> str:
    """Book a flight."""
    return f"Booked {flight} for {passenger}. Confirmation: FL{hash(flight)%10000:04d}"

@tool
def search_hotels(city: str, checkin: str, nights: int) -> str:
    """Search hotels in a city."""
    return f"Hotels in {city} for {nights} nights from {checkin}: Grand Hotel ($199/n), City Inn ($129/n)"

@tool
def book_hotel(hotel: str, guest: str, nights: int) -> str:
    """Book a hotel."""
    return f"Booked {hotel} for {guest}, {nights} nights. Confirmation: HT{hash(hotel)%10000:04d}"

# Sub-Agents
flight_agent = Agent(
    name="Flight Agent",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[search_flights, book_flight],
    instructions=["You handle flight searches and bookings.", "Book the cheapest option."],
)

hotel_agent = Agent(
    name="Hotel Agent",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[search_hotels, book_hotel],
    instructions=["You handle hotel searches and bookings.", "Book mid-range options."],
)

# Coordinator Tools
@tool
def delegate_to_flight_agent(task: str) -> str:
    """Delegate flight tasks to the Flight Agent."""
    result = flight_agent.run(task)
    return result.content if hasattr(result, 'content') else str(result)

@tool
def delegate_to_hotel_agent(task: str) -> str:
    """Delegate hotel tasks to the Hotel Agent."""
    result = hotel_agent.run(task)
    return result.content if hasattr(result, 'content') else str(result)

# Main Travel Agent
travel_agent = Agent(
    name="Travel Coordinator",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[delegate_to_flight_agent, delegate_to_hotel_agent],
    instructions=[
        "You coordinate travel bookings.",
        "Use Flight Agent for flights and Hotel Agent for hotels.",
        "Summarize all bookings at the end.",
    ],
)

if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Agent Travel (Agno + Gemini + Monocle)")
    print("=" * 60)

    query = "Book a flight on 2024-04-20 from SJC to SEA and hotel in Seattle for 5 nights starting 2024-04-20. Proceed with bookings."
    print(f"Query: {query}\n")

    result = travel_agent.run(query, stream=False)
    print(f"\nResult: {result.content if hasattr(result, 'content') else result}")

    print("\nWaiting for traces...")
    time.sleep(5)
    print("Done! Check Okahu.")
