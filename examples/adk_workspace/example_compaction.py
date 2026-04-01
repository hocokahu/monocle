"""
ADK Memory Compaction Example - Test script for monocle instrumentation.

This example demonstrates:
1. Setting up an ADK agent with event compaction enabled
2. Running multiple invocations to trigger compaction
3. Observing the compaction traces in monocle output

Usage:
    # First, create .env file with your API key:
    # GOOGLE_API_KEY=your-api-key-here

    # Then run:
    python example_compaction.py
"""

import asyncio
import os
import sys

# Add monocle to path for development testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../apptrace/src'))

from dotenv import load_dotenv
load_dotenv()

# Setup monocle telemetry BEFORE importing ADK
from monocle_apptrace.instrumentation.common.instrumentor import setup_monocle_telemetry

# Use default Okahu exporter (reads from OKAHU_INGESTION_ENDPOINT and OKAHU_API_KEY env vars)
setup_monocle_telemetry(
    workflow_name="adk_compaction_test"
)

# Now import ADK
from google.adk import Agent
from google.adk.apps import App
from google.adk.apps.app import EventsCompactionConfig
from google.adk.runners import InMemoryRunner
from google.genai import types


USER_ID = "test_user"
SESSION_ID = "test_session"


async def main():
    """Run ADK agent with memory compaction enabled."""

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: Please set GOOGLE_API_KEY in .env file")
        print("Create .env file with: GOOGLE_API_KEY=your-api-key-here")
        return

    # Create a simple agent
    root_agent = Agent(
        name="compaction_test_agent",
        model="gemini-2.0-flash",
        instruction="You are a helpful assistant that provides brief responses."
    )

    # Create app with event compaction configured
    # Using a very low interval (2) for testing purposes
    # Note: summarizer is created automatically from agent's model if not specified
    app = App(
        name="compaction_test_app",
        root_agent=root_agent,
        events_compaction_config=EventsCompactionConfig(
            compaction_interval=2,  # Compact every 2 invocations
            overlap_size=1,         # Keep 1 invocation overlap
        )
    )

    # Create runner with the app (this wires up compaction)
    runner = InMemoryRunner(app=app)

    # Create session via runner's session service
    session = await runner.session_service.create_session(
        app_name=app.name,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    print("\n=== ADK Memory Compaction Test ===\n")
    print("This test will run multiple agent invocations to trigger memory compaction.")
    print("Watch for 'memory.compaction' and 'memory.summarizer' spans in the output.\n")

    # List of test messages to send
    # Using 3 messages: compaction triggers after 2 invocations (compaction_interval=2)
    test_messages = [
        "What is 2 + 2?",
        "What is the capital of France?",
        "Tell me a short joke.",  # This should trigger compaction (3rd invocation)
    ]

    for i, message in enumerate(test_messages, 1):
        print(f"\n--- Invocation {i}: '{message}' ---")

        # Create user message content
        user_content = types.Content(
            role="user",
            parts=[types.Part(text=message)]
        )

        # Run agent and process events using run_async (production-style)
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=user_content,
        ):
            # Print agent responses
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        print(f"Agent: {part.text}")

            # Check if compaction happened
            if event.actions and event.actions.compaction:
                print(f"\n*** COMPACTION DETECTED after invocation {i}! ***")
                print(f"    Compacted range: {event.actions.compaction.start_timestamp} - {event.actions.compaction.end_timestamp}")

        await asyncio.sleep(0.5)  # Small delay between invocations

    print("\n=== Test Complete ===")
    print("Check the trace output above for 'memory.compaction' and 'memory.summarizer' spans.")

    await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
