"""
Migration script to remove tibia_character_name from users table
This field should only exist in user_characters table
"""
import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Migrate the database schema"""
    db_path = Path(__file__).parent / "tibia_bestiary.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"Migrating database at {db_path}")
    
    # Backup the database first
    backup_path = Path(__file__).parent / f"tibia_bestiary.db.backup_migration"
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created at {backup_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if tibia_character_name column exists in users table
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "tibia_character_name" in column_names:
            print("\n⚠️  Found tibia_character_name column in users table")
            print("Migrating to new schema...")
            
            # Step 1: Create new users table without tibia_character_name
            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    hashed_password VARCHAR(255) NOT NULL,
                    guild_rank VARCHAR(50),
                    join_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_superuser BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✓ Created new users table structure")
            
            # Step 2: Copy data from old table to new (excluding tibia_character_name)
            cursor.execute("""
                INSERT INTO users_new (
                    id, username, email, hashed_password, guild_rank, 
                    join_date, is_active, is_superuser, created_at
                )
                SELECT 
                    id, username, email, hashed_password, guild_rank,
                    join_date, is_active, is_superuser, created_at
                FROM users
            """)
            print("✓ Copied user data to new table")
            
            # Step 3: Check if we need to migrate character names to user_characters
            cursor.execute("""
                SELECT id, username, tibia_character_name 
                FROM users 
                WHERE tibia_character_name IS NOT NULL 
                AND tibia_character_name != ''
            """)
            users_with_chars = cursor.fetchall()
            
            if users_with_chars:
                print(f"\n⚠️  Found {len(users_with_chars)} users with character names")
                print("Migrating character names to user_characters table...")
                
                for user_id, username, char_name in users_with_chars:
                    # Check if character already exists in user_characters
                    cursor.execute("""
                        SELECT id FROM user_characters 
                        WHERE user_id = ? OR character_name = ?
                    """, (user_id, char_name))
                    
                    if not cursor.fetchone():
                        # Insert character into user_characters table
                        cursor.execute("""
                            INSERT INTO user_characters (user_id, character_name)
                            VALUES (?, ?)
                        """, (user_id, char_name))
                        print(f"  - Migrated character '{char_name}' for user '{username}'")
            
            # Step 4: Drop old table and rename new one
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")
            print("✓ Replaced old users table with new structure")
            
            # Step 5: Recreate indexes
            cursor.execute("CREATE UNIQUE INDEX idx_users_username ON users(username)")
            cursor.execute("CREATE UNIQUE INDEX idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX idx_users_id ON users(id)")
            print("✓ Recreated indexes")
            
            conn.commit()
            print("\n✅ Migration completed successfully!")
            return True
        else:
            print("✓ Database already has correct schema (no tibia_character_name in users)")
            return True
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        print(f"Restoring from backup...")
        conn.close()
        import shutil
        shutil.copy2(backup_path, db_path)
        print("✓ Database restored from backup")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE MIGRATION SCRIPT")
    print("Removing tibia_character_name from users table")
    print("=" * 60)
    print()
    
    if migrate_database():
        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETE")
        print("=" * 60)
        print("\nYou can now:")
        print("1. Run reset_users.py to create a fresh admin user")
        print("2. Restart the application")
    else:
        print("\n" + "=" * 60)
        print("❌ MIGRATION FAILED")
        print("=" * 60)
        print("\nPlease check the error messages above")
