import sqlite3
conn = sqlite3.connect('novel_agent.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print([t[0] for t in cursor.fetchall()])
conn.close()
