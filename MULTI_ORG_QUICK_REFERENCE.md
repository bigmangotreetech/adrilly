# Multi-Organization Support - Quick Reference

## Quick Start

### 1. Run Migration (One Time)
```bash
cd "adrilly web"
python migrate_users_multi_org.py
```

### 2. Verify Migration
```bash
python migrate_users_multi_org.py --verify
```

## Common Patterns

### Creating a User with Multiple Organizations

```python
from app.models.user import User
from bson import ObjectId

# Method 1: Using organization_ids parameter
user = User(
    phone_number='+1234567890',
    name='John Doe',
    email='john@example.com',
    role='coach',
    organization_ids=[ObjectId('org1'), ObjectId('org2')]
)

# Method 2: Using organization_id (auto-converted to array)
user = User(
    phone_number='+1234567890',
    name='John Doe',
    organization_id=ObjectId('org1')  # Becomes [ObjectId('org1')]
)
```

### Querying Users by Organization

```python
from bson import ObjectId

# Find all users in an organization
users = mongo.db.users.find({
    'organization_ids': ObjectId(org_id),
    'is_active': True
})

# Find users in multiple organizations (OR)
users = mongo.db.users.find({
    'organization_ids': {
        '$in': [ObjectId('org1'), ObjectId('org2')]
    }
})

# Find users in all specified organizations (AND)
users = mongo.db.users.find({
    'organization_ids': {
        '$all': [ObjectId('org1'), ObjectId('org2')]
    }
})
```

### Managing User Organizations

```python
from app.models.user import User
from bson import ObjectId

# Load user
user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
user = User.from_dict(user_data)

# Add to organization
if user.add_organization(ObjectId('new_org_id')):
    mongo.db.users.update_one(
        {'_id': user._id},
        {'$set': {'organization_ids': user.organization_ids}}
    )

# Remove from organization
if user.remove_organization(ObjectId('org_id')):
    mongo.db.users.update_one(
        {'_id': user._id},
        {'$set': {'organization_ids': user.organization_ids}}
    )

# Set primary organization
if user.set_primary_organization(ObjectId('primary_org_id')):
    mongo.db.users.update_one(
        {'_id': user._id},
        {'$set': {
            'organization_ids': user.organization_ids,
            'organization_id': user.organization_id
        }}
    )
```

### Accessing Organizations in Templates

```html
<!-- Current/Active Organization -->
{{ session.organization_id }}

<!-- All User's Organizations -->
{% for org_id in session.organization_ids %}
    {{ org_id }}
{% endfor %}
```

### Checking User Access

```python
from app.models.user import User

user = User.from_dict(user_data)

# Check if user can access an organization
if user.can_access_organization(org_id):
    # User has access
    pass

# Get all accessible organizations
org_ids = user.get_accessible_organizations()
```

## Session Management

### Setting Session on Login

```python
# In login route
organization_ids = user_data.get('organization_ids', [])
if not organization_ids and user_data.get('organization_id'):
    organization_ids = [str(user_data['organization_id'])]

session['organization_ids'] = [str(oid) for oid in organization_ids]
session['organization_id'] = str(organization_ids[0])  # Active org
```

### Switching Active Organization (Future Feature)

```python
@web_bp.route('/switch-organization/<org_id>')
@login_required
def switch_organization(org_id):
    # Verify user has access to this organization
    if org_id not in session.get('organization_ids', []):
        flash('Access denied', 'error')
        return redirect(url_for('web.dashboard'))
    
    # Switch active organization
    session['organization_id'] = org_id
    flash('Switched organization successfully', 'success')
    return redirect(url_for('web.dashboard'))
```

## Database Queries

### User Queries (Multi-Org Support)

```python
# ✅ CORRECT - Query users in organization
query = {'organization_ids': ObjectId(org_id)}
users = mongo.db.users.find(query)
```

### Entity Queries (Single-Org)

```python
# ✅ CORRECT - Query classes, groups, etc. in organization
query = {'organization_id': ObjectId(org_id)}
classes = mongo.db.classes.find(query)
```

### Mixed Queries (Stats Example)

```python
# Separate filters for users vs entities
user_filter = {'organization_ids': ObjectId(org_id)}
entity_filter = {'organization_id': ObjectId(org_id)}

# Count users
user_count = mongo.db.users.count_documents(user_filter)

# Count classes
class_count = mongo.db.classes.count_documents(entity_filter)
```

## Permission Checks

### Check User in Organization

```python
# Old way (single org) - Still works!
if str(user.get('organization_id')) == str(org_id):
    # Access granted
    pass

# New way (multi-org)
user_org_ids = user.get('organization_ids', [])
if not user_org_ids and user.get('organization_id'):
    user_org_ids = [user['organization_id']]

if ObjectId(org_id) in user_org_ids:
    # Access granted
    pass

# Best way (using model method)
user_obj = User.from_dict(user)
if user_obj.can_access_organization(org_id):
    # Access granted
    pass
```

## Common Mistakes to Avoid

### ❌ WRONG: Querying users with organization_id

```python
# This won't find users who have the org in organization_ids
users = mongo.db.users.find({'organization_id': ObjectId(org_id)})
```

### ✅ CORRECT: Query users with organization_ids

```python
# This finds all users who have org_id in their organization_ids array
users = mongo.db.users.find({'organization_ids': ObjectId(org_id)})
```

### ❌ WRONG: Querying entities with organization_ids

```python
# Classes belong to one organization only
classes = mongo.db.classes.find({'organization_ids': ObjectId(org_id)})
```

### ✅ CORRECT: Query entities with organization_id

```python
# Use organization_id for single-org entities
classes = mongo.db.classes.find({'organization_id': ObjectId(org_id)})
```

## Debugging

### Check User's Organizations

```python
from bson import ObjectId
user = mongo.db.users.find_one({'_id': ObjectId(user_id)})

print(f"organization_id: {user.get('organization_id')}")
print(f"organization_ids: {user.get('organization_ids')}")

# Verify they match
org_ids = user.get('organization_ids', [])
if user.get('organization_id') and user['organization_id'] in org_ids:
    print("✓ Consistency check passed")
else:
    print("⚠ Warning: organization_id not in organization_ids")
```

### Verify Session Data

```python
# In Flask route
print(f"User ID: {session.get('user_id')}")
print(f"Active Org: {session.get('organization_id')}")
print(f"All Orgs: {session.get('organization_ids')}")
```

### Check MongoDB Queries

```python
# Enable MongoDB query logging
import logging
logging.basicConfig()
logging.getLogger('pymongo').setLevel(logging.DEBUG)
```

## API Response Format

### User Object (JSON)

```json
{
  "_id": "user_id",
  "name": "John Doe",
  "email": "john@example.com",
  "role": "coach",
  "organization_id": "org_id_1",  // Primary org (backward compatibility)
  "organization_ids": ["org_id_1", "org_id_2", "org_id_3"],  // All orgs
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

## Helpful MongoDB Commands

### Find users with multiple organizations

```javascript
db.users.find({
  organization_ids: { $exists: true },
  $expr: { $gt: [{ $size: "$organization_ids" }, 1] }
})
```

### Find users with no organizations

```javascript
db.users.find({
  $or: [
    { organization_ids: { $exists: false } },
    { organization_ids: { $size: 0 } }
  ]
})
```

### Update user to add organization

```javascript
db.users.updateOne(
  { _id: ObjectId("user_id") },
  { 
    $addToSet: { organization_ids: ObjectId("org_id") },
    $set: { updated_at: new Date() }
  }
)
```

### Update user to remove organization

```javascript
db.users.updateOne(
  { _id: ObjectId("user_id") },
  { 
    $pull: { organization_ids: ObjectId("org_id") },
    $set: { updated_at: new Date() }
  }
)
```

## Testing

### Unit Test Example

```python
def test_user_multiple_organizations():
    """Test user with multiple organizations"""
    from app.models.user import User
    from bson import ObjectId
    
    org1 = ObjectId()
    org2 = ObjectId()
    org3 = ObjectId()
    
    # Create user
    user = User(
        phone_number='+1234567890',
        name='Test User',
        organization_ids=[org1, org2, org3]
    )
    
    # Test access
    assert user.can_access_organization(org1)
    assert user.can_access_organization(org2)
    assert user.can_access_organization(org3)
    assert not user.can_access_organization(ObjectId())
    
    # Test primary org
    assert user.organization_id == org1
    
    # Test accessible orgs
    accessible = user.get_accessible_organizations()
    assert len(accessible) == 3
```

## Need Help?

1. Check `MULTI_ORGANIZATION_SUPPORT.md` for detailed docs
2. Check `MULTI_ORG_CHANGES_SUMMARY.md` for migration info
3. Run verification: `python migrate_users_multi_org.py --verify`
4. Check MongoDB directly: `mongo your_database`

---

**Last Updated:** {{ current_date }}  
**Version:** 1.0  

