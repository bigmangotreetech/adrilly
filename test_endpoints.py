#!/usr/bin/env python3
"""
Simple endpoint test script to verify API routes are correctly configured
"""

import requests
import json

# Base URL for the API
BASE_URL = 'http://192.168.29.50:5000'

def test_health_endpoint():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health Check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_login_endpoint():
    """Test the login endpoint structure (without valid credentials)"""
    try:
        # Test with missing data to verify endpoint exists
        response = requests.post(f"{BASE_URL}/api/auth/login")
        print(f"Login Endpoint Test: {response.status_code}")
        if response.status_code == 400:  # Expected - missing request body
            print("✓ Login endpoint is accessible and returns expected error for missing data")
            return True
        else:
            print(f"Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"Login endpoint test failed: {e}")
        return False

def test_otp_request_endpoint():
    """Test the OTP request endpoint structure"""
    try:
        # Test with missing data to verify endpoint exists
        response = requests.post(f"{BASE_URL}/api/auth/request-otp")
        print(f"OTP Request Endpoint Test: {response.status_code}")
        if response.status_code == 400:  # Expected - missing request body
            print("✓ OTP request endpoint is accessible and returns expected error for missing data")
            return True
        else:
            print(f"Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"OTP request endpoint test failed: {e}")
        return False

def test_other_endpoints():
    """Test other API endpoint accessibility"""
    endpoints = [
        '/api/users',
        '/api/classes', 
        '/api/attendance',
        '/api/progress',
        '/api/payments',
        '/api/equipment'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}")
            print(f"{endpoint}: {response.status_code}")
            if response.status_code in [401, 403]:  # Expected - requires authentication
                print(f"✓ {endpoint} is accessible and requires authentication")
            elif response.status_code == 405:  # Method not allowed
                print(f"✓ {endpoint} is accessible but GET method not allowed")
            else:
                print(f"Response: {response.text[:100]}...")
        except Exception as e:
            print(f"{endpoint} test failed: {e}")

def main():
    """Run all endpoint tests"""
    print("Testing API Endpoints...")
    print("=" * 50)
    
    # Test health endpoint
    print("\n1. Testing Health Endpoint:")
    health_ok = test_health_endpoint()
    
    # Test authentication endpoints
    print("\n2. Testing Authentication Endpoints:")
    login_ok = test_login_endpoint()
    otp_ok = test_otp_request_endpoint()
    
    # Test other endpoints
    print("\n3. Testing Other API Endpoints:")
    test_other_endpoints()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Health Check: {'✓ PASS' if health_ok else '✗ FAIL'}")
    print(f"Login Endpoint: {'✓ PASS' if login_ok else '✗ FAIL'}")
    print(f"OTP Endpoint: {'✓ PASS' if otp_ok else '✗ FAIL'}")
    
    if health_ok and login_ok and otp_ok:
        print("\n🎉 All critical endpoints are properly configured!")
        print("\nExpected endpoints based on mobile app constants:")
        print("- /api/auth/request-otp")
        print("- /api/auth/verify-otp") 
        print("- /api/auth/login")
        print("- /api/auth/refresh")
        print("- /api/auth/profile")
        print("- /api/auth/logout")
        print("- /api/users/groups")
    else:
        print("\n⚠️  Some endpoints may need attention")

if __name__ == "__main__":
    main() 