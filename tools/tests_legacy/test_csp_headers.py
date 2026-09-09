#!/usr/bin/env python3
"""
Test script to verify CSP headers are correctly configured
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_admin_csp():
    """Test admin server CSP headers"""
    from app.admin.server import app
    
    print("\n" + "="*60)
    print("🧪 Testing Admin CSP Headers")
    print("="*60)
    
    with app.test_client() as client:
        # Test admin page CSP
        print("\n✅ Test 1: Admin Page CSP Headers")
        print("-" * 60)
        
        response = client.get('/admin')
        csp_header = response.headers.get('Content-Security-Policy', '')
        
        print(f"Status: {response.status_code}")
        print(f"CSP Header (first 100 chars):\n  {csp_header[:100]}...")
        
        # Check for required directives
        required_connects = [
            'localhost',
            '127.0.0.1',
            'cdnjs.cloudflare.com'
        ]
        
        all_found = True
        for conn in required_connects:
            if conn in csp_header:
                print(f"✅ Found '{conn}' in CSP connect-src")
            else:
                print(f"❌ Missing '{conn}' in CSP connect-src")
                all_found = False
        
        # Check for 0.0.0.0 (should NOT be there)
        if '0.0.0.0' in csp_header:
            print("❌ ERROR: CSP contains 0.0.0.0 (should not)")
            all_found = False
        else:
            print("✅ CSP correctly does NOT contain 0.0.0.0")
        
        if not all_found:
            print("\n⚠️  CSP may need adjustment")
            print(f"Full CSP: {csp_header}")
            return False
        
        print("\n✅ All CSP checks passed!")
        return True

if __name__ == '__main__':
    try:
        success = test_admin_csp()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
