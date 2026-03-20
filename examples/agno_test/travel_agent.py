"""
Simple Flight and Hotel Booking Agent using Agno + Gemini
With Monocle instrumentation for observability.

This demonstrates a basic travel booking agent with mock tools for:
- Searching flights
- Searching hotels
- Booking flights
- Booking hotels
"""

import time
from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools import tool

# ---------------------------------------------------------------------------
# Monocle Instrumentation Setup
# ---------------------------------------------------------------------------
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry

# Setup monocle with Okahu exporter
setup_monocle_telemetry(
    workflow_name="agno-travel-agent",
    monocle_exporters_list="okahu",
)

print("Monocle telemetry initialized with Okahu exporter")


# ---------------------------------------------------------------------------
# Mock Travel Tools
# ---------------------------------------------------------------------------

@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for available flights between two cities on a specific date.

    Args:
        origin: Departure city (e.g., "San Francisco")
        destination: Arrival city (e.g., "New York")
        date: Travel date in YYYY-MM-DD format

    Returns:
        List of available flights with prices
    """
    # Mock flight data
    flights = [
        {"flight": "UA123", "departure": "08:00", "arrival": "16:30", "price": "$350"},
        {"flight": "AA456", "departure": "12:00", "arrival": "20:15", "price": "$420"},
        {"flight": "DL789", "departure": "18:00", "arrival": "02:30+1", "price": "$280"},
    ]
    return f"Found {len(flights)} flights from {origin} to {destination} on {date}:\n" + \
           "\n".join([f"  - {f['flight']}: {f['departure']}-{f['arrival']}, {f['price']}" for f in flights])


@tool
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """Search for available hotels in a city for specific dates.

    Args:
        city: City name (e.g., "New York")
        checkin: Check-in date in YYYY-MM-DD format
        checkout: Check-out date in YYYY-MM-DD format

    Returns:
        List of available hotels with prices
    """
    # Mock hotel data
    hotels = [
        {"name": "Grand Plaza Hotel", "rating": "4.5 stars", "price": "$199/night"},
        {"name": "City Center Inn", "rating": "3.8 stars", "price": "$129/night"},
        {"name": "Luxury Suites", "rating": "4.9 stars", "price": "$450/night"},
    ]
    return f"Found {len(hotels)} hotels in {city} ({checkin} to {checkout}):\n" + \
           "\n".join([f"  - {h['name']}: {h['rating']}, {h['price']}" for h in hotels])


@tool
def book_flight(flight_number: str, passenger_name: str) -> str:
    """Book a specific flight for a passenger.

    Args:
        flight_number: The flight number to book (e.g., "UA123")
        passenger_name: Full name of the passenger

    Returns:
        Booking confirmation
    """
    confirmation = f"BK{hash(flight_number + passenger_name) % 100000:05d}"
    return f"Flight {flight_number} booked successfully for {passenger_name}. Confirmation: {confirmation}"


@tool
def book_hotel(hotel_name: str, guest_name: str, checkin: str, checkout: str) -> str:
    """Book a hotel room for a guest.

    Args:
        hotel_name: Name of the hotel to book
        guest_name: Full name of the guest
        checkin: Check-in date
        checkout: Check-out date

    Returns:
        Booking confirmation
    """
    confirmation = f"HT{hash(hotel_name + guest_name) % 100000:05d}"
    return f"Hotel '{hotel_name}' booked for {guest_name} ({checkin} to {checkout}). Confirmation: {confirmation}"


# ---------------------------------------------------------------------------
# Create Travel Agent
# ---------------------------------------------------------------------------

travel_agent = Agent(
    name="Travel Booking Agent",
    model=Gemini(id="gemini-2.0-flash"),
    tools=[search_flights, search_hotels, book_flight, book_hotel],
    instructions=[
        "You are a helpful travel booking assistant.",
        "Help users search for and book flights and hotels.",
        "Always confirm details before making bookings.",
        "Provide clear summaries of search results and bookings.",
    ],
    markdown=True,
)


# ---------------------------------------------------------------------------
# Run Agent
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Travel Booking Agent (Agno + Gemini + Monocle)")
    print("=" * 60)
    print()

    # Test query - direct booking without confirmation
    query = """
    Book flight DL789 and hotel "City Center Inn" for John Smith.
    Check-in: 2024-04-15, Check-out: 2024-04-18.
    Proceed with bookings immediately.
    """

    print(f"User Query: {query.strip()}")
    print()
    print("-" * 60)
    print()

    travel_agent.print_response(query, stream=True)

    # Wait a bit to ensure traces are flushed to Okahu
    print()
    print("-" * 60)
    print("Waiting for traces to be exported to Okahu...")
    time.sleep(5)
    print("Done! Check Okahu for traces.")
