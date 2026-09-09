#!/usr/bin/env python3
"""
Debug Edge TTS voice structure
"""
import asyncio
import json

async def inspect_voices():
    try:
        import edge_tts
        print("Fetching voices...")
        voices = await edge_tts.list_voices()
        
        print(f"\nTotal voices: {len(voices)}")
        print("\n🔍 Inspecting voice structure (first 3 voices):\n")
        
        for i, voice in enumerate(voices[:3]):
            print(f"Voice {i+1}:")
            if isinstance(voice, dict):
                for key, value in voice.items():
                    print(f"  {key}: {value}")
            else:
                print(f"  Type: {type(voice)}")
                print(f"  Value: {voice}")
            print()
        
        # Test zh-CN voices
        print("\n🇨🇳 Checking zh-CN voices:")
        zh_cn = [v for v in voices if isinstance(v, dict) and v.get('Locale', '').startswith('zh-CN')]
        
        if zh_cn:
            voice = zh_cn[0]
            print(f"\nFirst zh-CN voice structure:")
            for key, value in voice.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(inspect_voices())
