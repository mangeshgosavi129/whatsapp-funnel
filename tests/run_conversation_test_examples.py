#!/usr/bin/env python3
"""
Example usage of the WhatsApp Conversation Simulator Test

This script demonstrates how to run the live conversation test
with different configurations.
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_live_whatsapp_conversations import run_whatsapp_conversation_test


async def main():
    """Run the WhatsApp conversation simulator test with example configurations."""
    
    print("🚀 WhatsApp Conversation Simulator Test Examples")
    print("=" * 50)
    
    # Example 1: Quick test with fast message delays
    print("\n📱 Example 1: Quick Test (1s delay)")
    print("Running a quick test with 1-second delays between messages...")
    
    results1 = await run_whatsapp_conversation_test(
        message_delay=1.0,
        cleanup_after=False,
        validate_results=True
    )
    
    print(f"✅ Quick test completed in {results1['duration_seconds']:.2f} seconds")
    
    # Example 2: Realistic test with normal delays
    print("\n📱 Example 2: Realistic Test (2.5s delay)")
    print("Running a realistic test with 2.5-second delays...")
    
    results2 = await run_whatsapp_conversation_test(
        message_delay=2.5,
        cleanup_after=False,
        validate_results=True
    )
    
    print(f"✅ Realistic test completed in {results2['duration_seconds']:.2f} seconds")
    
    # Example 3: Test with cleanup
    print("\n📱 Example 3: Test with Cleanup")
    print("Running a test and cleaning up data afterwards...")
    
    results3 = await run_whatsapp_conversation_test(
        message_delay=1.5,
        cleanup_after=True,
        validate_results=True
    )
    
    print(f"✅ Test with cleanup completed in {results3['duration_seconds']:.2f} seconds")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"Example 1 - Success: {results1['setup_successful'] and results1['simulation_successful']}")
    print(f"Example 2 - Success: {results2['setup_successful'] and results2['simulation_successful']}")
    print(f"Example 3 - Success: {results3['setup_successful'] and results3['simulation_successful']}")
    
    if results1['validation_results']:
        total_messages = (
            results1['validation_results']['statistics']['total_messages'] +
            results2['validation_results']['statistics']['total_messages'] +
            results3['validation_results']['statistics']['total_messages']
        )
        print(f"Total messages created across all tests: {total_messages}")


if __name__ == "__main__":
    asyncio.run(main())
