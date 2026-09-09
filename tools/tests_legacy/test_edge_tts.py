#!/usr/bin/env python3
"""
Test Edge TTS functionality directly
"""
import asyncio
import sys

async def test_edge_tts_voices():
    """Test fetching voices from Edge TTS"""
    try:
        import edge_tts
        print("✅ edge_tts imported successfully")
        
        print("\n⏳ Fetching voices (this may take 5-30 seconds on first call)...")
        voices = await edge_tts.list_voices()
        
        print(f"✅ Successfully fetched {len(voices)} voices!")
        
        # Show sample voices
        print("\n📋 Sample voices:")
        for i, voice in enumerate(voices[:5]):
            print(f"  {i+1}. {voice.get('ShortName')} - {voice.get('DisplayName')}")
        
        # Filter zh-CN voices
        zh_cn_voices = [v for v in voices if v.get('Locale', '').startswith('zh-CN')]
        print(f"\n🔤 Found {len(zh_cn_voices)} Chinese (Simplified) voices:")
        for voice in zh_cn_voices[:5]:
            print(f"  • {voice.get('DisplayName')} ({voice.get('Gender')})")
        
        # Test a simple synthesis
        print("\n🎙️ Testing voice synthesis...")
        communicate = edge_tts.Communicate(
            text="Hello, this is a test.",
            voice="en-US-AriaNeural"
        )
        
        chunks = []
        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                chunks.append(chunk)
        
        print(f"✅ Synthesis successful! Generated {len(chunks)} audio chunks")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("🧪 Testing Edge TTS functionality...\n")
    success = asyncio.run(test_edge_tts_voices())
    
    if success:
        print("\n✅ All Edge TTS tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Edge TTS tests failed!")
        sys.exit(1)
