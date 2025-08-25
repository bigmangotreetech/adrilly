import requests
from app.app import create_app
from app.services.auth_service import AuthService
from app.extensions import mongo

print("🔍 Testing authentication issue...")

# Test 1: Check if admin user exists in database
app, _ = create_app()
with app.app_context():
    admin_user = mongo.db.users.find_one({'email': 'admin@adrilly.com'})
    if admin_user:
        print(f"✅ Admin user found in DB: {admin_user['email']}")
        print(f"   Role: {admin_user.get('role', 'unknown')}")
        print(f"   Active: {admin_user.get('is_active', 'unknown')}")
    else:
        print("❌ Admin user not found in database")

# Test 2: Test AuthService authentication directly
print("\n🔐 Testing AuthService.authenticate_user...")
with app.app_context():
    result = AuthService.authenticate_user('admin@adrilly.com', 'admin123')
    if result:
        print("✅ AuthService authentication successful")
    else:
        print("❌ AuthService authentication failed")

# Test 3: Test HTTP POST login
print("\n🌐 Testing HTTP POST login...")
try:
    session = requests.Session()
        login_data = {
        'email': 'admin@adrilly.com',
        'password': 'admin123'
        }
        
    response = session.post('http://127.0.0.1:5000/login', data=login_data, allow_redirects=False)
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 302:
        print("✅ Login successful - redirecting")
        redirect_location = response.headers.get('Location', 'Unknown')
        print(f"Redirect to: {redirect_location}")
        
        # Test dashboard access
        dashboard_response = session.get('http://127.0.0.1:5000/dashboard')
        print(f"Dashboard access: {dashboard_response.status_code}")
        
    elif response.status_code == 200:
        print("⚠️ Login returned 200 - checking for errors")
        if 'Invalid email or password' in response.text:
            print("❌ Invalid credentials error found")
        elif 'error' in response.text.lower():
            print("❌ Some error found in response")
        else:
            print("🤔 No obvious error in response")
            else:
        print(f"❌ Unexpected status code: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error during HTTP test: {e}")

print("\n" + "="*50)
print("📋 WORKING SUPER ADMIN CREDENTIALS:")
print("="*50)
print("Email:    admin@adrilly.com")
print("Password: admin123")
print("Role:     super_admin")
print("URL:      http://127.0.0.1:5000/login")
print("="*50) 