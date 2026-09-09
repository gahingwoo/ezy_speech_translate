#!/usr/bin/env python3
"""
Test script to verify Edge TTS audio synthesis is working correctly.
Helps debug audio playback issues.
"""

import asyncio
import edge_tts
import io
import sys
import os

async def test_synthesis():
    """Test Edge TTS audio synthesis with detailed diagnostics."""
    
    test_text = "This is a test of the Edge TTS audio synthesis system."
    test_voice = "zh-CN-XiaoxiaoNeural"
    
    print(f"🔧 Testing Edge TTS Audio Synthesis")
    print(f"  Text: {test_text}")
    print(f"  Voice: {test_voice}")
    print()
    
    try:
        audio_buffer = io.BytesIO()
        chunk_count = 0
        total_bytes = 0
        
        print("📡 Starting synthesis...")
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
                    print(f"  ✓ Audio chunk {chunk_count}: {len(audio_data)} bytes")
            elif chunk_type == 'log':
                log_msg = chunk.get('message', '')
                print(f"  📝 Log: {log_msg}")
            else:
                print(f"  ℹ️ Other chunk type: {chunk_type}")
        
        audio_buffer.seek(0)
        audio_data = audio_buffer.getvalue()
        
        print()
        print(f"✅ Synthesis completed")
        print(f"  Total chunks: {chunk_count}")
        print(f"  Total audio bytes: {total_bytes}")
        print(f"  Final buffer size: {len(audio_data)}")
        
        if audio_data:
            # Check for MP3 headers
            header_hex = audio_data[:4].hex()
            print(f"  Header bytes: {header_hex}")
            
            # Validate MP3
            is_valid_mp3 = (audio_data[:2] == b'\xff\xfb' or  # MPEG frame sync
                           audio_data[:2] == b'\xff\xfa' or   # MPEG frame sync
                           audio_data[:3] == b'ID3')          # ID3 tag
            
            if is_valid_mp3:
                print(f"  ✅ Valid MP3 file detected")
            else:
                print(f"  ⚠️ Audio may not be valid MP3 (header: {header_hex})")
            
            # Save test file
            test_file = '/tmp/test_edge_tts.mp3'
            with open(test_file, 'wb') as f:
                f.write(audio_data)
            print(f"  📁 Saved to: {test_file}")
            print(f"     Size: {len(audio_data) / 1024:.1f} KB")
            
            # Try compression if ffmpeg is available
            print()
            print("🔄 Testing compression with ffmpeg...")
            result = os.system('which ffmpeg > /dev/null 2>&1')
            if result == 0:
                print("  ✓ ffmpeg is available")
                
                # Test compression
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
                    output_path = output_file.name
                
                compress_cmd = [
                    'ffmpeg',
                    '-i', test_file,
                    '-q:a', '9',
                    '-ac', '1',
                    '-ar', '16000',
                    '-y',
                    output_path
                ]
                
                import subprocess
                result = subprocess.run(compress_cmd, capture_output=True, timeout=10)
                
                if result.returncode == 0 and os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        compressed = f.read()
                    
                    ratio = (1 - len(compressed) / len(audio_data)) * 100
                    print(f"  ✅ Compression successful")
                    print(f"     Original: {len(audio_data) / 1024:.1f} KB")
                    print(f"     Compressed: {len(compressed) / 1024:.1f} KB ({ratio:.1f}% smaller)")
                    
                    # Check compressed file header
                    comp_header_hex = compressed[:4].hex()
                    print(f"     Header: {comp_header_hex}")
                    
                    # Clean up
                    os.unlink(output_path)
                else:
                    print(f"  ❌ Compression failed")
                    if result.stderr:
                        print(f"     Error: {result.stderr.decode()[:200]}")
            else:
                print("  ⚠️ ffmpeg not available")
        else:
            print(f"  ❌ No audio data returned!")
        
        return True
        
    except Exception as e:
        print(f"❌ Synthesis failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("Edge TTS Audio Synthesis Test")
    print("=" * 50)
    print()
    
    success = asyncio.run(test_synthesis())
    sys.exit(0 if success else 1)
