#!/usr/bin/env python3
"""
Quick script to reset user files
"""
import json

# Reset users.json to only include you
users = {
    "corysmth14@gmail.com": {
        "first_name": "cory",
        "email": "corysmth14@gmail.com",
        "approved_at": "2025-08-06 22:16:46.032184",
        "status": "active"
    }
}

# Reset pending users to empty
pending = {}

# Write files
with open('users.json', 'w') as f:
    json.dump(users, f, indent=2)

with open('pending_users.json', 'w') as f:
    json.dump(pending, f, indent=2)

print("✅ User files reset successfully!")
print("- users.json: Contains only corysmth14@gmail.com")
print("- pending_users.json: Empty")