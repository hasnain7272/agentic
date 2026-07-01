import sqlite3
import json

conn = sqlite3.connect('kernel.db')
cursor = conn.cursor()

cursor.execute("SELECT id, config FROM tenants")
for row in cursor.fetchall():
    print(f"Tenant: {row[0]}")
    print(f"Config: {row[1]}")

cursor.execute("SELECT id, context FROM sessions")
for row in cursor.fetchall():
    print(f"Session: {row[0]}")
    print(f"Context: {row[1]}")

conn.close()
