#!/usr/bin/env python
"""Working LangGraph client example using the SDK"""

import asyncio
from langgraph_sdk import get_client


async def main():
    # Connect to the LangGraph server
    client = get_client(url="http://localhost:8101")

    # Create a thread
    thread = await client.threads.create()
    print(f"Created thread: {thread['thread_id']}")

    # Send a message to the mr_poet assistant
    print("\nSending message: 'Write a short poem about coding'")
    print("\n=== Stream Events ===")

    # Stream the response
    async for chunk in client.runs.stream(
        thread["thread_id"],
        "mr_poet",  # assistant name from langgraph.json
        input={"messages": [{"role": "user", "content": "Write a short poem about coding"}]},
        stream_mode="updates"  # Changed to "updates" to see node outputs
    ):
        print(f"\nEvent: {chunk.event}")
        if chunk.data:
            print(f"Data: {chunk.data}")

    print("\n=== Final Thread State ===")
    # Get the final state
    state = await client.threads.get_state(thread["thread_id"])
    if "values" in state and "messages" in state["values"]:
        for msg in state["values"]["messages"]:
            if hasattr(msg, "content"):
                print(f"\n{msg.type}: {msg.content}")


if __name__ == "__main__":
    asyncio.run(main())
