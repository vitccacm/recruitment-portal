#!/usr/bin/env python3
"""
Database Management Tool for ACM Recruitment Portal
Run this script to perform database operations like migrations, backups, etc.
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Membership


def print_header():
    print("\n" + "=" * 50)
    print("  ACM Recruitment Portal - Database Manager")
    print("=" * 50)


def print_menu():
    print("\nSelect an action:")
    print("  1. Migrate Membership table (add first_name, last_name, is_archived)")
    print("  2. View all tables")
    print("  3. View Membership records")
    print("  4. Reset database (DANGEROUS - drops all tables)")
    print("  0. Exit")
    print()


def migrate_membership_table(app):
    """Migrate the Membership table to new schema"""
    print("\n--- Migrating Membership Table ---")
    
    with app.app_context():
        # Check current table structure
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        
        if 'memberships' not in inspector.get_table_names():
            print("Memberships table doesn't exist. Creating fresh...")
            db.create_all()
            print("✓ All tables created successfully!")
            return
        
        columns = [col['name'] for col in inspector.get_columns('memberships')]
        print(f"Current columns: {columns}")
        
        # Check if migration is needed
        if 'first_name' in columns and 'last_name' in columns:
            print("✓ Table already has first_name and last_name columns. No migration needed.")
            return
        
        # Perform migration using raw SQL
        print("\nPerforming migration...")
        
        try:
            # For SQLite, we need to recreate the table
            if 'sqlite' in str(db.engine.url):
                print("Detected SQLite database. Recreating table...")
                
                # Check if there's existing data
                result = db.session.execute(text("SELECT COUNT(*) FROM memberships")).scalar()
                
                if result > 0:
                    print(f"Found {result} existing records. Migrating data...")
                    
                    # Create backup of existing data
                    existing_data = db.session.execute(text("SELECT id, email, name, created_at FROM memberships")).fetchall()
                    
                    # Drop old table
                    db.session.execute(text("DROP TABLE memberships"))
                    db.session.commit()
                    
                    # Create new table
                    db.create_all()
                    
                    # Migrate data - split name into first_name and last_name
                    for row in existing_data:
                        name_parts = (row[2] or "Unknown").split(' ', 1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ""
                        
                        membership = Membership(
                            email=row[1],
                            first_name=first_name,
                            last_name=last_name,
                            is_archived=False
                        )
                        db.session.add(membership)
                    
                    db.session.commit()
                    print(f"✓ Migrated {len(existing_data)} records successfully!")
                else:
                    # No data, just drop and recreate
                    db.session.execute(text("DROP TABLE memberships"))
                    db.session.commit()
                    db.create_all()
                    print("✓ Table recreated successfully (was empty)!")
            else:
                # For MySQL/PostgreSQL, use ALTER TABLE
                print("Detected MySQL/PostgreSQL. Altering table...")
                
                if 'name' in columns and 'first_name' not in columns:
                    # Add new columns
                    db.session.execute(text("ALTER TABLE memberships ADD COLUMN first_name VARCHAR(50)"))
                    db.session.execute(text("ALTER TABLE memberships ADD COLUMN last_name VARCHAR(50)"))
                    db.session.execute(text("ALTER TABLE memberships ADD COLUMN is_archived BOOLEAN DEFAULT FALSE"))
                    
                    # Migrate data from name to first_name/last_name
                    db.session.execute(text("""
                        UPDATE memberships 
                        SET first_name = SUBSTRING_INDEX(name, ' ', 1),
                            last_name = TRIM(SUBSTRING(name, LOCATE(' ', name) + 1))
                    """))
                    
                    # Make columns NOT NULL
                    db.session.execute(text("ALTER TABLE memberships MODIFY first_name VARCHAR(50) NOT NULL"))
                    db.session.execute(text("ALTER TABLE memberships MODIFY last_name VARCHAR(50) NOT NULL"))
                    
                    # Optionally drop old name column
                    db.session.execute(text("ALTER TABLE memberships DROP COLUMN name"))
                    
                    db.session.commit()
                    print("✓ Migration completed successfully!")
                
        except Exception as e:
            db.session.rollback()
            print(f"✗ Migration failed: {e}")
            return
    
    print("✓ Migration complete!")


def view_tables(app):
    """View all database tables"""
    print("\n--- Database Tables ---")
    
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        for table in tables:
            columns = inspector.get_columns(table)
            print(f"\n{table}:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"  - {col['name']}: {col['type']} {nullable}")


def view_memberships(app):
    """View all membership records"""
    print("\n--- Membership Records ---")
    
    with app.app_context():
        from sqlalchemy import text
        
        try:
            # Try new schema first
            result = db.session.execute(text(
                "SELECT id, first_name, last_name, email, is_archived, created_at FROM memberships ORDER BY created_at DESC"
            )).fetchall()
            
            if not result:
                print("No membership records found.")
                return
            
            print(f"\n{'ID':<5} {'First Name':<15} {'Last Name':<15} {'Email':<30} {'Archived':<10} {'Created'}")
            print("-" * 95)
            
            for row in result:
                archived = "Yes" if row[4] else "No"
                created = row[5].strftime('%Y-%m-%d') if row[5] else "N/A"
                print(f"{row[0]:<5} {row[1]:<15} {row[2]:<15} {row[3]:<30} {archived:<10} {created}")
                
        except Exception as e:
            # Fall back to old schema
            try:
                result = db.session.execute(text(
                    "SELECT id, name, email, created_at FROM memberships ORDER BY created_at DESC"
                )).fetchall()
                
                print("(Using old schema - migration needed)")
                print(f"\n{'ID':<5} {'Name':<30} {'Email':<30} {'Created'}")
                print("-" * 75)
                
                for row in result:
                    created = row[3].strftime('%Y-%m-%d') if row[3] else "N/A"
                    print(f"{row[0]:<5} {row[1]:<30} {row[2]:<30} {created}")
            except:
                print(f"Error reading memberships: {e}")


def reset_database(app):
    """Reset the entire database (DANGEROUS)"""
    print("\n--- Reset Database ---")
    print("⚠️  WARNING: This will DELETE ALL DATA in the database!")
    
    confirm = input("Type 'RESET' to confirm: ")
    if confirm != 'RESET':
        print("Reset cancelled.")
        return
    
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Recreate default admin
        from app.models import Admin
        if not Admin.query.filter_by(email='admin').first():
            admin = Admin(email='admin', name='Super Admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        
        print("✓ Database reset complete. Default admin recreated.")


def main():
    app = create_app()
    
    print_header()
    
    while True:
        print_menu()
        
        try:
            choice = input("Enter choice (0-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting...")
            break
        
        if choice == '0':
            print("\nGoodbye!")
            break
        elif choice == '1':
            migrate_membership_table(app)
        elif choice == '2':
            view_tables(app)
        elif choice == '3':
            view_memberships(app)
        elif choice == '4':
            reset_database(app)
        else:
            print("Invalid choice. Please try again.")


if __name__ == '__main__':
    main()
