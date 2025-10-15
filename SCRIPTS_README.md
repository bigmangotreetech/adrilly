# Migration Scripts - Independent & Ready to Use

All migration scripts are now **100% independent** and don't require Flask or your application to be running!

## 🚀 Quick Start

### Option 1: Simple Migration (Recommended)
```bash
python migrate_now.py
```
✅ Fastest  
✅ No prompts  
✅ Auto-verifies  

### Option 2: Detailed Migration
```bash
python update_users_to_multi_org.py
```
✅ Shows progress  
✅ Asks confirmation  
✅ Detailed output  

## 📋 Requirements

Just one package:
```bash
pip install pymongo
```

That's it! No Flask, no app dependencies.

## 🔧 Configuration

Scripts auto-detect MongoDB connection from:

### 1. Environment Variable (Recommended)
```bash
export MONGODB_URI="mongodb://localhost:27017/your_database"
python migrate_now.py
```

### 2. config.py File
Scripts will read from `config.py` if it exists:
```python
class Config:
    MONGODB_URI = "mongodb://localhost:27017/your_database"
```

### 3. Default Fallback
If nothing is set, uses:
```
mongodb://localhost:27017/coaching_app
```

## 📖 Usage Examples

### Basic Usage
```bash
# Just run it
python migrate_now.py
```

### With Custom MongoDB URI
```bash
# Linux/Mac
export MONGODB_URI="mongodb://user:pass@host:27017/database"
python migrate_now.py

# Windows CMD
set MONGODB_URI=mongodb://user:pass@host:27017/database
python migrate_now.py

# Windows PowerShell
$env:MONGODB_URI="mongodb://user:pass@host:27017/database"
python migrate_now.py
```

### Verify Migration
```bash
python update_users_to_multi_org.py --verify
```

### Get Help
```bash
python migrate_now.py --help
python update_users_to_multi_org.py --help
```

## 🎯 What Each Script Does

### `migrate_now.py`
- ⚡ Quick & simple
- No prompts, just runs
- Shows progress every 10 users
- Auto-verifies at the end
- Perfect for quick migrations

### `update_users_to_multi_org.py`
- 📊 Detailed & interactive
- Asks for confirmation
- Shows each user update
- Detailed reporting
- Verification option
- Best for production

## ✅ Expected Output

```
============================================================
MULTI-ORGANIZATION MIGRATION
============================================================

Connecting to MongoDB...
URI: mongodb://localhost:27017/coaching_app
Database: coaching_app

✓ Connected to MongoDB successfully!

Found 150 users in database
Starting migration...
------------------------------------------------------------
  Processed 10/150 users...
  Processed 20/150 users...
  ...
------------------------------------------------------------

✓ Migration complete!
  Total users:      150
  Updated:          145
  Already migrated: 5

Verifying migration...
  Users with organization_ids: 150/150

✅ SUCCESS! All users migrated successfully!

============================================================
Next steps:
1. Restart your application
2. Test user login and organization features
============================================================
```

## 🔍 Troubleshooting

### "pymongo not installed"
```bash
pip install pymongo
```

### "Failed to connect to MongoDB"
Check if MongoDB is running:
```bash
# Linux/Mac
sudo systemctl status mongod

# Or try connecting directly
mongo
```

### "No module named 'config'"
This is OK! Script will use environment variable or default.

### Wrong database
Set the correct MongoDB URI:
```bash
export MONGODB_URI="mongodb://localhost:27017/your_actual_database"
```

## 🎉 Features

✅ **Independent** - No Flask required  
✅ **Auto-detect** - Reads config automatically  
✅ **Safe** - Skips already migrated users  
✅ **Fast** - Bulk operations  
✅ **Verified** - Auto-verification  
✅ **Portable** - Works anywhere  

## 📞 Support

Having issues?

1. Check MongoDB is running: `mongo`
2. Verify connection string: `echo $MONGODB_URI`
3. Test connection: `mongo $MONGODB_URI`
4. Check script output for specific errors

## 🔄 Migration Process

Each script:
1. Connects to MongoDB directly
2. Finds all users
3. Checks if already migrated (skips if yes)
4. Converts `organization_id` → `organization_ids` array
5. Updates database
6. Verifies all users migrated
7. Shows summary

## 💡 Pro Tips

1. **Backup first**: `mongodump --db your_database --out backup/`
2. **Test locally**: Run on dev database first
3. **Verify after**: Use `--verify` flag to double-check
4. **Re-run safe**: Scripts skip already migrated users
5. **Keep simple**: Use `migrate_now.py` for quick migrations

---

**No Flask. No Dependencies. Just Works.** ✨

