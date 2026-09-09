#!/usr/bin/env python3
"""
Diagnostic script for Edge TTS in production environment
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_edge_tts_import():
    """Test if edge_tts can be imported"""
    print("\n" + "="*70)
    print("🧪 Test 1: Edge TTS Module Import")
    print("="*70)
    
    try:
        import edge_tts
        print(f"✅ edge_tts imported successfully")
        print(f"   Version: {edge_tts.__version__ if hasattr(edge_tts, '__version__') else 'unknown'}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import edge_tts: {e}")
        return False

def test_edge_tts_subprocess():
    """Test if edge_tts can be called via subprocess"""
    print("\n" + "="*70)
    print("🧪 Test 2: Edge TTS via Subprocess")
    print("="*70)
    
    import subprocess
    import json
    
    code = """
import asyncio
import edge_tts
import sys
import json

try:
    async def fetch():
        voices = await edge_tts.list_voices()
        return voices
    
    voices = asyncio.run(fetch())
    print(json.dumps(voices))
except Exception as e:
    print(f"ERROR: {str(e)}", file=sys.stderr)
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"❌ Subprocess failed with return code {result.returncode}")
            print(f"   stderr: {result.stderr[:200]}")
            return False
        
        if not result.stdout.strip():
            print(f"❌ Subprocess returned empty output")
            return False
        
        voices = json.loads(result.stdout)
        print(f"✅ Successfully fetched {len(voices)} voices via subprocess")
        if voices:
            print(f"   Sample voice: {voices[0].get('ShortName', 'N/A')}")
        return True
        
    except subprocess.TimeoutExpired:
        print(f"❌ Subprocess timeout after 30 seconds")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse subprocess JSON: {e}")
        print(f"   stdout (first 300 chars): {result.stdout[:300]}")
        return False
    except Exception as e:
        print(f"❌ Subprocess test error: {e}")
        return False

def test_user_server_config():
    """Test if user server's /api/tts/cache-stats returns valid JSON"""
    print("\n" + "="*70)
    print("🧪 Test 3: User Server /api/tts/cache-stats")
    print("="*70)
    
    try:
        from app.user.server import app, SYNTHESIS_REQUEST_CACHE, EDGE_TTS_AVAILABLE
        
        print(f"   EDGE_TTS_AVAILABLE: {EDGE_TTS_AVAILABLE}")
        print(f"   SYNTHESIS_REQUEST_CACHE type: {type(SYNTHESIS_REQUEST_CACHE)}")
        print(f"   SYNTHESIS_REQUEST_CACHE items: {len(SYNTHESIS_REQUEST_CACHE)}")
        
        with app.test_client() as client:
            response = client.get('/api/tts/cache-stats')
            
            print(f"   Response status: {response.status_code}")
            print(f"   Response content-type: {response.headers.get('Content-Type')}")
            
            if response.status_code != 200:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"   Body (first 200 chars): {response.get_data(as_text=True)[:200]}")
                return False
            
            # Check if response is JSON
            try:
                data = response.get_json()
                print(f"✅ /api/tts/cache-stats returned valid JSON")
                print(f"   success: {data.get('success')}")
                print(f"   cache_items: {data.get('cache_items')}")
                print(f"   cache_size_mb: {data.get('cache_size_mb')}")
                return data.get('success') == True
            except Exception as e:
                print(f"❌ Response is not valid JSON: {e}")
                body = response.get_data(as_text=True)
                print(f"   Body (first 300 chars): {body[:300]}")
                return False
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all diagnostic tests"""
    print("\n" + "="*70)
    print("🔍 Edge TTS Production Environment Diagnostic")
    print("="*70)
    
    results = []
    
    # Test 1: Import
    results.append(("Edge TTS Import", test_edge_tts_import()))
    
    # Test 2: Subprocess
    results.append(("Edge TTS Subprocess", test_edge_tts_subprocess()))
    
    # Test 3: User Server API
    results.append(("User Server API", test_user_server_config()))
    
    # Summary
    print("\n" + "="*70)
    print("📊 Test Summary")
    print("="*70)
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Edge TTS is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed. Check the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
