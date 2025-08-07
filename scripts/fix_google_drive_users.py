#!/usr/bin/env python3
"""
Fix Google Drive user files by uploading clean versions
"""
import json

# Clean users.json (only you)
clean_users = {
    "corysmth14@gmail.com": {
        "first_name": "cory", 
        "email": "corysmth14@gmail.com",
        "approved_at": "2025-08-06 22:16:46.032184",
        "status": "active"
    }
}

# Empty pending users
clean_pending = {}

# Save clean files locally
with open('users.json', 'w') as f:
    json.dump(clean_users, f, indent=2)
    
with open('pending_users.json', 'w') as f:
    json.dump(clean_pending, f, indent=2)

print("✅ Created clean user files:")
print("- users.json: Only contains corysmth14@gmail.com") 
print("- pending_users.json: Empty")
print("\n📤 Now these clean files will upload to Google Drive when you use the app!")