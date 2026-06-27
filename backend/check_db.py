import sqlite3
conn = sqlite3.connect("srp.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM \"{t}\"")
    cnt = cursor.fetchone()[0]
    print(f"  {t}: {cnt} rows")
conn.close()
