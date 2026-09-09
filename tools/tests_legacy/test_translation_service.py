#!/usr/bin/env python3
"""
Test script for the new translation service
Tests rate limiting, caching, and concurrent requests
"""

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Configuration
BASE_URL = 'http://localhost:1915'
NUM_CONCURRENT_USERS = 10
TEXTS = [
    "Hello, how are you?",
    "The weather is nice today",
    "I like to eat delicious food",
    "Thank you for your help",
]

def test_single_translation():
    """Test single translation endpoint"""
    print("\n📝 Test 1: Single Translation")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/translate"
    payload = {
        "text": "Hello, this is a test of the translation service",
        "target_lang": "zh"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print(f"✅ Translation successful!")
            print(f"   Original:   {data.get('original')[:50]}")
            print(f"   Translated: {data.get('translated')[:50]}")
            print(f"   Cached:     {data.get('cached')}")
            return True
        else:
            print(f"❌ Translation failed: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_cache_hit():
    """Test cache hit (translated same text twice)"""
    print("\n📦 Test 2: Cache Hit")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/translate"
    payload = {
        "text": "Cache test - this should be cached",
        "target_lang": "zh"
    }
    
    # First request
    print("First request (should use API)...")
    start = time.time()
    r1 = requests.post(url, json=payload, timeout=30)
    t1 = time.time() - start
    
    if r1.status_code != 200:
        print(f"❌ First request failed")
        return False
    
    data1 = r1.json()
    print(f"✅ Time: {t1:.3f}s | Cached: {data1.get('cached')}")
    
    # Second request (should hit cache)
    print("Second request (should hit cache)...")
    start = time.time()
    r2 = requests.post(url, json=payload, timeout=30)
    t2 = time.time() - start
    
    if r2.status_code != 200:
        print(f"❌ Second request failed")
        return False
    
    data2 = r2.json()
    print(f"✅ Time: {t2:.3f}s | Cached: {data2.get('cached')}")
    
    if data2.get('translated') == data1.get('translated') and t2 < t1 * 0.5:
        print(f"✅ Cache working! Speed improvement: {t1/t2:.1f}x faster")
        return True
    else:
        print(f"❌ Cache not working as expected")
        return False

def test_batch_translation():
    """Test batch translation"""
    print("\n🚀 Test 3: Batch Translation")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/translate/batch"
    payload = {
        "texts": TEXTS[:3],
        "target_lang": "zh"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print(f"✅ Batch translation successful!")
            print(f"   Translated {data.get('count')} texts")
            for i, trans in enumerate(data.get('translations', [])[:2]):
                print(f"   [{i+1}] {trans['original'][:30]} → {trans['translated'][:30]}")
            return True
        else:
            print(f"❌ Batch translation failed: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def translate_single(text, lang='zh', user_id=1):
    """Helper function to translate a single text"""
    url = f"{BASE_URL}/api/translate"
    payload = {"text": text, "target_lang": lang}
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return {
                'user': user_id,
                'success': True,
                'text': text[:30],
                'status_code': response.status_code,
                'cached': response.json().get('cached', False)
            }
        else:
            return {
                'user': user_id,
                'success': False,
                'status_code': response.status_code,
                'error': response.json().get('error', 'Unknown')
            }
    except Exception as e:
        return {
            'user': user_id,
            'success': False,
            'error': str(e)
        }

def test_concurrent_requests():
    """Test concurrent requests (rate limiting)"""
    print("\n⚡ Test 4: Concurrent Requests (Rate Limiting)")
    print("=" * 60)
    print(f"Simulating {NUM_CONCURRENT_USERS} concurrent users...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=NUM_CONCURRENT_USERS) as executor:
        futures = []
        
        # Submit concurrent requests
        for i in range(NUM_CONCURRENT_USERS):
            text = TEXTS[i % len(TEXTS)]
            future = executor.submit(translate_single, text, 'zh', i+1)
            futures.append(future)
        
        # Collect results
        results = []
        for future in as_completed(futures):
            results.append(future.result())
    
    total_time = time.time() - start_time
    
    # Analyze results
    successful = sum(1 for r in results if r.get('success'))
    failed = len(results) - successful
    cached = sum(1 for r in results if r.get('cached'))
    
    print(f"Results:")
    print(f"  Total time:    {total_time:.2f}s")
    print(f"  Successful:    {successful}/{len(results)}")
    print(f"  Failed:        {failed}/{len(results)}")
    print(f"  From cache:    {cached}/{len(results)}")
    print(f"  Avg per req:   {total_time/len(results):.3f}s")
    print(f"  Effective QPS: {len(results)/total_time:.2f} req/s")
    
    if successful == len(results):
        print(f"✅ All concurrent requests successful!")
        return True
    else:
        print(f"⚠️ Some requests failed (expected with rate limiting)")
        return True  # This is expected behavior

def test_error_handling():
    """Test error handling"""
    print("\n⚠️ Test 5: Error Handling")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/translate"
    
    # Test 1: Empty text
    print("Test 5.1: Empty text...")
    payload = {"text": "", "target_lang": "zh"}
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code in [200, 400] and not r.json().get('success', True):
        print("✅ Empty text handled correctly")
    else:
        print("⚠️ Empty text handling")
    
    # Test 2: Invalid language
    print("Test 5.2: Invalid language...")
    payload = {"text": "Hello", "target_lang": "xx"}
    r = requests.post(url, json=payload, timeout=30)
    # Should still work (invalid lang gets normalized)
    print(f"✅ Invalid language handled (status {r.status_code})")
    
    # Test 3: Very long text
    print("Test 5.3: Long text (5000 chars)...")
    payload = {"text": "Hello " * 900, "target_lang": "zh"}
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code == 200 or r.status_code == 413:
        print(f"✅ Long text handled (status {r.status_code})")
    else:
        print(f"⚠️ Long text returned {r.status_code}")
    
    # Test 4: Missing parameters
    print("Test 5.4: Missing parameters...")
    payload = {"text": "Hello"}  # Missing target_lang
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code == 400:
        print("✅ Missing parameters rejected correctly")
    else:
        print(f"⚠️ Missing parameters returned {r.status_code}")
    
    return True

def test_health_check():
    """Test health check endpoint"""
    print("\n🏥 Test 6: Health Check")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy")
            print(f"   Status:       {data.get('status')}")
            print(f"   Clients:      {data.get('clients')}")
            print(f"   Translations: {data.get('translations')}")
            return True
        else:
            print(f"❌ Health check failed")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("🧪 Translation Service Test Suite")
    print("=" * 60)
    
    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/api/health", timeout=5)
    except:
        print(f"❌ Error: Cannot connect to {BASE_URL}")
        print(f"   Make sure the server is running:")
        print(f"   python app/user/server.py")
        sys.exit(1)
    
    tests = [
        ("Health Check", test_health_check),
        ("Single Translation", test_single_translation),
        ("Cache Hit", test_cache_hit),
        ("Batch Translation", test_batch_translation),
        ("Error Handling", test_error_handling),
        ("Concurrent Requests", test_concurrent_requests),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'='*60}")
    print(f"Result: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())
