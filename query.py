import sqlite3
import json

conn = sqlite3.connect('kernel.db')
c = conn.cursor()
c.execute("SELECT id, name, config FROM tenants")
for row in c.fetchall():
    print(f"Tenant ID: {row[0]}, Name: {row[1]}")
    try:
        cfg = json.loads(row[2]) if row[2] else {}
        print("Config BYOM:")
        for cfg_item in cfg.get("byom_configs", []):
            print(f"  - ID: {cfg_item.get('id')}, Model: {cfg_item.get('model')}, BaseURL: {cfg_item.get('base_url')}")
    except Exception as e:
        print(f"Error: {e}")
