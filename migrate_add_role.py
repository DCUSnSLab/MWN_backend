#!/usr/bin/env python3
"""
Migration script to add the missing 'role' column to the users table.
This fixes the "column users.role does not exist" error.
"""

import os
import sys
import psycopg2
from datetime import datetime

def connect_to_db():
    """Connect to PostgreSQL database"""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://myuser:mypassword@127.0.0.1:5432/weather_notification')
    print(f"Connecting to database...")
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return None

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table"""
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s AND column_name = %s
    """, (table_name, column_name))
    return cursor.fetchone() is not None

def add_role_column(cursor):
    """Add the role column to users table"""
    print("Checking if 'role' column exists in users table...")
    
    if check_column_exists(cursor, 'users', 'role'):
        print("✅ 'role' column already exists")
        return True
    
    print("Adding 'role' column to users table...")
    try:
        # Add the role column with default value 'user'
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN role VARCHAR(20) DEFAULT 'user'
        """)
        
        # Update any existing null values
        cursor.execute("""
            UPDATE users 
            SET role = 'user' 
            WHERE role IS NULL OR role = ''
        """)
        
        print("✅ Successfully added 'role' column")
        return True
        
    except Exception as e:
        print(f"❌ Failed to add 'role' column: {e}")
        return False

def verify_migration(cursor):
    """Verify the migration was successful"""
    print("\nVerifying migration...")
    
    try:
        # Check if column exists
        if not check_column_exists(cursor, 'users', 'role'):
            print("❌ 'role' column still missing")
            return False
        
        # Check user counts by role
        cursor.execute("""
            SELECT role, COUNT(*) as count 
            FROM users 
            GROUP BY role
        """)
        results = cursor.fetchall()
        
        print("User counts by role:")
        for role, count in results:
            print(f"  - {role}: {count} users")
        
        # Test a simple query that was failing before
        cursor.execute("SELECT id, email, role FROM users LIMIT 1")
        result = cursor.fetchone()
        if result:
            print(f"✅ Test query successful: user {result[0]} has role '{result[2]}'")
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def main():
    print("=" * 60)
    print("PostgreSQL Users Table Migration - Add Role Column")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Connect to database
    conn = connect_to_db()
    if not conn:
        return 1
    
    cursor = conn.cursor()
    
    try:
        # Add role column
        if not add_role_column(cursor):
            return 1
        
        # Commit changes
        conn.commit()
        print("✅ Changes committed to database")
        
        # Verify migration
        if not verify_migration(cursor):
            return 1
        
        print("\n🎉 Migration completed successfully!")
        print("\nThe backend API should now work correctly.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return 1
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    sys.exit(main())