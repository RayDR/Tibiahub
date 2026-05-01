import sqlite3
import os

DB_FILE = "tibia_bestiary.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print("Database file not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]

        if "tibia_character_name" not in columns:
            print("Adding tibia_character_name column...")
            cursor.execute("ALTER TABLE users ADD COLUMN tibia_character_name VARCHAR(100)")
            cursor.execute("CREATE UNIQUE INDEX ix_users_tibia_character_name ON users (tibia_character_name)")

        if "guild_rank" not in columns:
            print("Adding guild_rank column...")
            cursor.execute("ALTER TABLE users ADD COLUMN guild_rank VARCHAR(50)")

        if "join_date" not in columns:
            print("Adding join_date column...")
            cursor.execute("ALTER TABLE users ADD COLUMN join_date DATETIME")

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
