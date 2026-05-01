"""
Reset user tables and create admin user
"""
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
from app.models.user import User
from app.models.user_character import UserCharacter
from app.core.security import get_password_hash
from datetime import datetime
import sys

def reset_users(db: Session):
    """Delete all users and characters"""
    print("Deleting all users and characters...")
    db.query(UserCharacter).delete()
    db.query(User).delete()
    db.commit()
    print("✓ All users and characters deleted")

def create_admin_user(db: Session):
    """Create admin superuser"""
    print("\nCreating admin user...")
    
    admin = User(
        username="admin",
        email="admin@tibiabestiary.com",
        hashed_password=get_password_hash("admin123"),
        guild_rank="Leader",
        join_date=datetime.utcnow(),
        is_active=True,
        is_superuser=True
    )
    
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    print(f"✓ Admin user created:")
    print(f"  - Username: {admin.username}")
    print(f"  - Email: {admin.email}")
    print(f"  - Password: admin123")
    print(f"  - Is Superuser: {admin.is_superuser}")
    print(f"  - Guild Rank: {admin.guild_rank}")
    
    return admin

def main():
    """Main function"""
    db = SessionLocal()
    
    try:
        print("=" * 50)
        print("RESETTING USER DATABASE")
        print("=" * 50)
        
        # Ask for confirmation
        response = input("\n⚠️  This will DELETE all users and characters. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            sys.exit(0)
        
        # Reset users
        reset_users(db)
        
        # Create admin
        admin = create_admin_user(db)
        
        print("\n" + "=" * 50)
        print("✓ DATABASE RESET COMPLETE")
        print("=" * 50)
        print("\nYou can now login with:")
        print("  Username: admin")
        print("  Password: admin123")
        print("\nChange the password after first login!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
