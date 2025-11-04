#!/usr/bin/env python
"""Test script for A2A agent communication"""
import asyncio
from user_facing_agent.agent import root_agent


async def test_history_question():
    """Test with a history question"""
    print("=" * 60)
    print("Testing StudentHelperAgent with history question...")
    print("=" * 60)

    question = "What is the French Revolution?"
    print(f"\nQuestion: {question}\n")

    responses = []
    async for event in root_agent.run_live(question):
        if hasattr(event, 'text'):
            print(event.text, end="", flush=True)
            responses.append(event.text)
        else:
            print(event, end="", flush=True)
            responses.append(str(event))

    print("\n")
    return "".join(str(r) for r in responses)


async def test_philosophy_question():
    """Test with a philosophy question"""
    print("=" * 60)
    print("Testing StudentHelperAgent with philosophy question...")
    print("=" * 60)

    question = "What is Plato's Theory of Forms?"
    print(f"\nQuestion: {question}\n")

    responses = []
    async for event in root_agent.run_live(question):
        if hasattr(event, 'text'):
            print(event.text, end="", flush=True)
            responses.append(event.text)
        else:
            print(event, end="", flush=True)
            responses.append(str(event))

    print("\n")
    return "".join(str(r) for r in responses)


async def main():
    """Run all tests"""
    print("\n>>> Starting A2A System Tests\n")

    # Test 1: History question (should route to HistoryHelperAgent on port 8001)
    await test_history_question()

    # Test 2: Philosophy question (should route to PhilosophyHelperAgent on port 8002)
    await test_philosophy_question()

    print("=" * 60)
    print("[OK] All A2A tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
