#!/usr/bin/env python3
"""
Diagnostic script for Edge TTS on AlmaLinux production servers.
Tests for network connectivity and Edge TTS availability.
"""

import asyncio
import sys
import os
import time

async def test_edge_tts(test_count=3):
    """Test Edge TTS with detailed error reporting for production diagnosis."""
    
    print("=" * 60)
    print("EzySpeechTranslate Edge TTS Diagnostic Tool")
    print("=" * 60)
    print()
    
    # Check Python version
    print(f"🔍 Environment Check:")
    print(f"   Python version: {sys.version}")
    print(f"   Platform: {sys.platform}")
    print()
    
    # Check for ffmpeg
    print(f"🔍 ffmpeg status:")
    result = os.system('which ffmpeg > /dev/null 2>&1')
    if result == 0:
        print(f"   ✅ ffmpeg is installed")
        os.system('ffmpeg -version | head -1')
    else:
        print(f"   ❌ ffmpeg is NOT installed")
        print(f"      Install with: yum install ffmpeg  (on AlmaLinux/RHEL)")
    print()
    
    # Test Edge TTS import
    print(f"🔍 Testing edge-tts import:")
    try:
        import edge_tts
        print(f"   ✅ edge-tts imported successfully")
        print(f"      Module path: {edge_tts.__file__}")
    except ImportError as e:
        print(f"   ❌ Failed to import edge-tts: {e}")
        return False
    print()
    
    # Test TTS synthesis multiple times to detect rate limiting
    test_text = "This is a test of the Edge TTS audio synthesis system."
    test_voice = "en-US-AriaNeural"
    
    print(f"🔍 Testing Edge TTS synthesis (multiple attempts to detect rate limiting):")
    print(f"   Text: {test_text}")
    print(f"   Voice: {test_voice}")
    print(f"   Attempts: {test_count}")
    print()
    
    success_count = 0
    failure_count = 0
    
    for attempt in range(1, test_count + 1):
        print(f"📡 Attempt {attempt}/{test_count}...")
        
        try:
            import io
            audio_buffer = io.BytesIO()
            chunk_count = 0
            total_bytes = 0
            
            communicate = edge_tts.Communicate(
                text=test_text,
                voice=test_voice,
                rate="+0%"
            )
            
            async for chunk in communicate.stream():
                chunk_type = chunk.get('type', 'unknown')
                
                if chunk_type == 'audio':
                    audio_data = chunk.get('data', b'')
                    if audio_data:
                        audio_buffer.write(audio_data)
                        chunk_count += 1
                        total_bytes += len(audio_data)
            
            audio_buffer.seek(0)
            final_audio = audio_buffer.getvalue()
            
            if final_audio and len(final_audio) > 0:
                # Check MP3 validity
                is_valid_mp3 = False
                if len(final_audio) >= 2:
                    first_byte = final_audio[0]
                    second_byte = final_audio[1]
                    if first_byte == 0xff and (second_byte & 0xe0) == 0xe0:
                        is_valid_mp3 = True
                    if len(final_audio) >= 3 and final_audio[:3] == b'ID3':
                        is_valid_mp3 = True
                
                if is_valid_mp3:
                    print(f"   ✅ Attempt {attempt}: SUCCESS ({len(final_audio)} bytes)")
                    success_count += 1
                else:
                    print(f"   ⚠️ Attempt {attempt}: Audio generated but format unrecognized")
                    failure_count += 1
            else:
                print(f"   ❌ Attempt {attempt}: No audio data returned")
                failure_count += 1
        
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Attempt {attempt}: FAILED")
            print(f"      Error: {error_msg[:100]}")
            failure_count += 1
            
            # Diagnose specific errors
            if '403' in error_msg:
                print(f"      🔍 Diagnosis: 403 Forbidden - Rate limiting or service restriction")
            elif 'Connection' in error_msg or 'refused' in error_msg:
                print(f"      🔍 Diagnosis: Connection error")
        
        # Wait between attempts to avoid hammering the service
        if attempt < test_count:
            print(f"      Waiting 2 seconds before next attempt...\n")
            await asyncio.sleep(2)
    
    print()
    print("=" * 60)
    print(f"📊 Test Results:")
    print(f"   Successful: {success_count}/{test_count}")
    print(f"   Failed: {failure_count}/{test_count}")
    
    if success_count == test_count:
        print("✅ All checks passed - Edge TTS is working correctly")
        return True
    elif success_count > 0 and failure_count > 0:
        print("⚠️ Edge TTS working intermittently")
        print("   This suggests rate limiting or service instability")
        print("   Recommendation: Wait a few minutes before retrying")
        return False
    else:
        print("❌ All checks failed - Edge TTS service is unavailable")
        return False

if __name__ == '__main__':
    print()
    
    # Run test with 3 attempts to detect rate limiting
    success = asyncio.run(test_edge_tts(test_count=3))
    
    print()
    print("=" * 60)
    sys.exit(0 if success else 1)
