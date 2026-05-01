"""
Migration script to add new fields to events table and create public_event_participants table
Run this script to update the database schema for the enhanced event system
"""
import sqlite3
import os

DB_FILE = "tibia_bestiary.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"❌ Database file not found: {DB_FILE}")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        print("🔄 Starting events migration...")
        
        # Check if events table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        if not cursor.fetchone():
            print("⚠️  Events table doesn't exist. Creating it from scratch...")
            cursor.execute("""
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid VARCHAR(36) UNIQUE NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    rules TEXT,
                    reward VARCHAR(500),
                    start_date DATETIME NOT NULL,
                    end_date DATETIME,
                    draw_date DATETIME,
                    total_slots INTEGER,
                    entry_cost VARCHAR(200),
                    winner_id INTEGER,
                    winner_number INTEGER,
                    is_drawn BOOLEAN DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'active',
                    is_active BOOLEAN DEFAULT 1,
                    is_public BOOLEAN DEFAULT 0,
                    participant_mode VARCHAR(20) DEFAULT 'manual',
                    active_days_limit INTEGER DEFAULT 10,
                    guild_name VARCHAR(200),
                    guild_world VARCHAR(100),
                    creator_id INTEGER NOT NULL,
                    announcement_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (creator_id) REFERENCES users (id),
                    FOREIGN KEY (winner_id) REFERENCES users (id),
                    FOREIGN KEY (announcement_id) REFERENCES announcements (id)
                )
            """)
            print("✅ Events table created")
        else:
            # Check existing columns
            cursor.execute("PRAGMA table_info(events)")
            existing_columns = [info[1] for info in cursor.fetchall()]
            
            # Add new columns if they don't exist
            new_columns = {
                "participant_mode": "VARCHAR(20) DEFAULT 'manual'",
                "active_days_limit": "INTEGER DEFAULT 10",
                "guild_name": "VARCHAR(200)",
                "guild_world": "VARCHAR(100)",
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    print(f"  Adding column: {column_name}...")
                    cursor.execute(f"ALTER TABLE events ADD COLUMN {column_name} {column_def}")
                    print(f"  ✅ Added {column_name}")
                else:
                    print(f"  ⏭️  Column {column_name} already exists")
        
        # Create public_event_participants table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='public_event_participants'")
        if not cursor.fetchone():
            print("\n🔄 Creating public_event_participants table...")
            cursor.execute("""
                CREATE TABLE public_event_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    character_name VARCHAR(100) NOT NULL,
                    character_level INTEGER,
                    character_vocation VARCHAR(50),
                    character_world VARCHAR(100),
                    last_login VARCHAR(100),
                    assigned_number INTEGER,
                    is_auto_loaded BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (event_id) REFERENCES events (id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX ix_public_participants_event_id ON public_event_participants (event_id)")
            cursor.execute("CREATE INDEX ix_public_participants_character_name ON public_event_participants (character_name)")
            
            print("✅ public_event_participants table created with indexes")
        else:
            print("\n⏭️  public_event_participants table already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
        # Show summary
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        print(f"\n📊 Summary:")
        print(f"   - Events in database: {event_count}")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Events Database Migration Script")
    print("=" * 60)
    migrate()
    print("=" * 60)
