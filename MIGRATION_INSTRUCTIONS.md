# Migration Instructions - Multi-Organization Support

## Quick Migration Guide

### Step 1: Backup Your Database

**IMPORTANT:** Always backup before running migrations!

```bash
# For MongoDB
mongodump --db your_database_name --out backup/

# Verify backup was created
ls -la backup/
```

### Step 2: Run the Migration Script

```bash
cd "adrilly web"
python update_users_to_multi_org.py
```

The script will:
- Show you how many users need migration
- Ask for confirmation before proceeding
- Update all users to have `organization_ids` array
- Show progress for each user
- Provide a summary at the end
- Automatically verify the migration

### Step 3: Verify the Migration (Optional)

If you want to verify again later:

```bash
python update_users_to_multi_org.py --verify
```

### Step 4: Restart Your Application

```bash
# Stop your application
# Then start it again
python run.py
```

### Step 5: Test Everything

- ✅ Login with existing users
- ✅ View users list
- ✅ Create new users
- ✅ Test organization filtering
- ✅ Check user permissions

## What the Script Does

### For Each User:

**Before:**
```json
{
  "_id": "user123",
  "name": "John Doe",
  "organization_id": "org456"
}
```

**After:**
```json
{
  "_id": "user123",
  "name": "John Doe",
  "organization_id": "org456",
  "organization_ids": ["org456"]
}
```

### Special Cases:

1. **Users already migrated**: Skipped (no changes)
2. **Users with no organization**: Gets empty array `[]`
3. **Users with organization_id**: Gets array with one item `[org_id]`

## Expected Output

```
======================================================================
UPDATING USERS TO MULTI-ORGANIZATION SUPPORT
======================================================================

📊 Found 150 total users in database

✅ Already migrated:  0
🔄 Need migration:    150
⚠️  No organization:  0

🚀 Starting migration of 150 users...
----------------------------------------------------------------------
✓ 1/150: Updated 'John Doe' (ID: 507f1f77bcf86cd799439011)
✓ 2/150: Updated 'Jane Smith' (ID: 507f1f77bcf86cd799439012)
...
----------------------------------------------------------------------

======================================================================
MIGRATION COMPLETE
======================================================================
Total users:       150
Already migrated:  0
Updated now:       150
Errors:            0
======================================================================

✅ SUCCESS: All users have been migrated to multi-organization support!

Next steps:
1. Restart your application
2. Test user login and organization features
3. Verify users can access their organizations
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'app'"

**Solution:** Make sure you're in the correct directory:
```bash
cd "adrilly web"
python update_users_to_multi_org.py
```

### Issue: "Database connection failed"

**Solution:** 
1. Make sure MongoDB is running
2. Check your `.env` or `config.py` for correct database settings
3. Verify your connection string

### Issue: "Some users had errors"

**Solution:**
1. Check the error messages in the output
2. Verify those users exist in the database
3. Check if there are any MongoDB constraints
4. You can re-run the script - it will skip already migrated users

### Issue: Migration shows "0 need migration"

**Possible causes:**
1. ✅ Migration already completed (good!)
2. Run verification to confirm: `python update_users_to_multi_org.py --verify`

## Rollback (If Needed)

If you need to rollback the migration:

```python
# rollback_migration.py
from app import create_app
from app.extensions import mongo

app = create_app()
with app.app_context():
    result = mongo.db.users.update_many(
        {},
        {'$unset': {'organization_ids': ''}}
    )
    print(f"Removed organization_ids from {result.modified_count} users")
```

Or restore from backup:
```bash
mongorestore --db your_database_name backup/your_database_name
```

## Verification Commands

### Check Total Users
```bash
python update_users_to_multi_org.py --verify
```

### Manual MongoDB Check
```javascript
// Connect to MongoDB
mongo your_database_name

// Count users with organization_ids
db.users.count({ organization_ids: { $exists: true } })

// Count total users
db.users.count()

// Find users without organization_ids
db.users.find({ organization_ids: { $exists: false } }, { name: 1, organization_id: 1 })

// Find users with multiple organizations
db.users.find({ $expr: { $gt: [{ $size: "$organization_ids" }, 1] } })
```

## Command Reference

```bash
# Run migration (with confirmation)
python update_users_to_multi_org.py

# Verify migration
python update_users_to_multi_org.py --verify

# Show help
python update_users_to_multi_org.py --help
```

## FAQ

**Q: Will this break my existing application?**  
A: No, the changes are backward compatible. The old `organization_id` field is kept.

**Q: What if I add the script runs but updates 0 users?**  
A: The migration might already be complete. Run `--verify` to check.

**Q: Can I run the script multiple times?**  
A: Yes! The script skips already migrated users.

**Q: What if a user has no organization?**  
A: They get an empty array `[]` for `organization_ids`.

**Q: How long does migration take?**  
A: Usually very fast. ~1000 users in a few seconds.

**Q: Can I migrate just some users?**  
A: Yes, modify the script to filter specific users before the loop.

## Need Help?

1. Check the error message in the script output
2. Verify your database connection
3. Check MongoDB logs
4. Review `MULTI_ORGANIZATION_SUPPORT.md` for details
5. Run verification to see current state

## Success Checklist

After migration:
- [ ] Script completed without errors
- [ ] Verification shows all users have `organization_ids`
- [ ] Application starts successfully
- [ ] Users can login
- [ ] Organization filtering works
- [ ] No console errors
- [ ] All tests pass (if you have tests)

---

**Migration Complete?** ✅  
**Backup Created?** ✅  
**Verification Passed?** ✅  
**Application Tested?** ✅  

