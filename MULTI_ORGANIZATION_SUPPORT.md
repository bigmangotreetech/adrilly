# Multi-Organization Support

## Overview
This document describes the changes made to support users belonging to multiple organizations simultaneously.

## Database Schema Changes

### User Model (`app/models/user.py`)

#### New Fields
- **`organization_ids`**: Array of ObjectId - Contains all organizations the user belongs to
- **`organization_id`**: ObjectId (retained for backward compatibility) - Points to the primary/first organization

#### Key Changes
1. **Constructor Updated**: Now accepts both `organization_id` (single) and `organization_ids` (array)
   - If `organization_ids` is provided, it takes precedence
   - If only `organization_id` is provided, it's converted to a single-item array
   - `organization_id` always points to the first item in `organization_ids`

2. **New Methods**:
   - `add_organization(organization_id)`: Add user to an additional organization
   - `remove_organization(organization_id)`: Remove user from an organization
   - `set_primary_organization(organization_id)`: Set which organization is primary

3. **Updated Methods**:
   - `can_access_organization()`: Now checks if org_id is in the `organization_ids` array
   - `get_accessible_organizations()`: Returns array of all organization IDs
   - `to_dict()`: Includes both `organization_id` and `organization_ids`
   - `from_dict()`: Handles both old (single org) and new (multi-org) data

## Session Management Changes

### Login Flow (`app/routes/web.py`)

When a user logs in:
1. Both `organization_ids` (array) and `organization_id` (active/primary org) are stored in session
2. Default active organization is set to the first one in the array
3. Backward compatibility maintained for users with only `organization_id`

```python
session['organization_ids'] = [str(oid) for oid in organization_ids]
session['organization_id'] = str(organization_ids[0])  # Active org
```

### Updated Routes

The `login_required` decorator now:
- Loads `organization_ids` from database if not in session
- Sets active `organization_id` to first organization
- Maintains backward compatibility for existing users

## Query Changes

### User Queries

All user queries have been updated to filter by `organization_ids` instead of `organization_id`:

**Before:**
```python
query = {'organization_id': ObjectId(org_id)}
```

**After:**
```python
query = {'organization_ids': ObjectId(org_id)}
```

This uses MongoDB's array query feature - documents match if the org_id exists anywhere in the `organization_ids` array.

### Affected Routes

#### `app/routes/web.py`
- `/users` - User management page
- `/export_users` - User export functionality
- `/payments/user/<user_id>` - User payment checks

#### `app/routes/users.py`
- `/api/users` - Get users endpoint
- `/api/users/groups` - Create group (coach validation)
- `/api/users/organizations/stats` - Organization statistics
- `/api/users/<user_id>/children` - Child profile creation

## Backward Compatibility

### Existing Data
- Users with only `organization_id` field will automatically work
- The `from_dict()` method converts single `organization_id` to `organization_ids` array
- `organization_id` field is maintained for backward compatibility

### Session Handling
- Login flow handles both old and new user data structures
- Users without `organization_ids` get it populated from `organization_id`

## Usage Examples

### Creating a User in Multiple Organizations

```python
from app.models.user import User
from bson import ObjectId

# Create user with multiple organizations
user = User(
    phone_number='+1234567890',
    name='John Doe',
    email='john@example.com',
    role='coach',
    organization_ids=[
        ObjectId('org1_id'),
        ObjectId('org2_id'),
        ObjectId('org3_id')
    ]
)
```

### Adding User to Another Organization

```python
user = User.from_dict(user_data)
success = user.add_organization(ObjectId('new_org_id'))
if success:
    mongo.db.users.update_one(
        {'_id': user._id},
        {'$set': {'organization_ids': user.organization_ids}}
    )
```

### Querying Users in an Organization

```python
# Find all users in a specific organization
users = mongo.db.users.find({
    'organization_ids': ObjectId(org_id),
    'is_active': True
})
```

### Switching Active Organization (Future Feature)

```python
# This can be implemented as a route
@web_bp.route('/switch-organization/<org_id>')
@login_required
def switch_organization(org_id):
    user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    org_ids = user.get('organization_ids', [])
    
    if ObjectId(org_id) in org_ids:
        session['organization_id'] = str(org_id)
        flash('Switched organization successfully', 'success')
    else:
        flash('Access denied', 'error')
    
    return redirect(url_for('web.dashboard'))
```

## Important Notes

### Entity Ownership
- **Users**: Can belong to multiple organizations (multi-org)
- **Organizations, Centers, Classes, Groups, Schedules**: Belong to ONE organization only
- **Payments**: Associated with ONE organization (where the payment was made)

### Query Patterns

**For User Queries (multi-org support):**
```python
query = {'organization_ids': ObjectId(org_id)}
```

**For Entity Queries (single org):**
```python
query = {'organization_id': ObjectId(org_id)}
```

## Migration Path

### For Existing Databases

Run this migration script to add `organization_ids` to existing users:

```python
from app.extensions import mongo
from bson import ObjectId

def migrate_users_to_multi_org():
    users = mongo.db.users.find({})
    
    for user in users:
        if 'organization_ids' not in user and user.get('organization_id'):
            # Convert single org_id to array
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'organization_ids': [user['organization_id']]
                    }
                }
            )
            print(f"Migrated user {user['_id']}")
    
    print("Migration complete!")

if __name__ == '__main__':
    migrate_users_to_multi_org()
```

## Testing Checklist

- [ ] Login with existing users (single org)
- [ ] Login with new users (multiple orgs)
- [ ] Create new users in multiple organizations
- [ ] View users list (filtered by organization)
- [ ] Create child profiles (inherit parent's orgs)
- [ ] Export users to CSV
- [ ] View user payments (permission check)
- [ ] Organization statistics (user counts)

## Future Enhancements

1. **Organization Switcher UI**: Add dropdown in navigation to switch between organizations
2. **Organization-Specific Permissions**: Allow different roles in different organizations
3. **Organization Invitations**: Allow users to be invited to additional organizations
4. **Organization Transfer**: Move users between organizations (update primary org)

