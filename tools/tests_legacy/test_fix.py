#!/usr/bin/env python3
"""
Test that Edge TTS voices can be fetched without eventlet conflicts
"""

# First test: Import with the fix
print("Testing eventlet + asyncio compatibility fix...")

import eventlet
import eventlet.wsgi
# CRITICAL: Disable select monkeypatch
eventlet.monkey_patch(select=False)
print("✓ eventlet imported with select=False")

import asyncio
import edge_tts

print("✓ asyncio and edge_tts imported successfully")

async def test_fetch():
    """Test fetching voices"""
    try:
        print("\n⏳ Fetching Edge TTS voices...")
        voices = await edge_tts.list_voices()
        print(f"✅ Successfully fetched {len(voices)} voices!")
        
        zh_cn = [v for v in voices if v.get('Locale', '').startswith('zh-CN')]
        print(f"   • Found {len(zh_cn)} Chinese (Simplified) voices")
        
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test using asyncio.run (this is what the fixed code does)
print("\nTesting with asyncio.run()...")
success = asyncio.run(test_fetch())

if success:
    print("\n✅ All tests passed! The fix works correctly.")
else:
    print("\n❌ Tests failed. There's still an issue.")
