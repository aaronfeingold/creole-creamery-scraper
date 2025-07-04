#!/usr/bin/env python3
"""
Script to clear all entries from the hall_of_fame_entries table.
Run this before running the scraper again to get the correct chronological order.
"""

import os
import psycopg2
from dotenv import load_dotenv


def clear_database():
    """Clear all entries from the hall_of_fame_entries table."""
    # Load environment variables
    load_dotenv()

    db_url = os.environ.get("NEON_DATABASE_URL")
    if not db_url:
        print("Error: NEON_DATABASE_URL environment variable not found")
        print("Make sure you have a .env file with your database URL")
        return False

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Check if table exists
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'hall_of_fame_entries'
                    );
                """
                )
                table_exists = cur.fetchone()[0]

                if not table_exists:
                    print("Table 'hall_of_fame_entries' doesn't exist yet.")
                    return True

                # Get current count
                cur.execute("SELECT COUNT(*) FROM hall_of_fame_entries")
                current_count = cur.fetchone()[0]

                if current_count == 0:
                    print("Table is already empty.")
                    return True

                print(f"Found {current_count} entries in the database.")
                confirm = input(
                    "Are you sure you want to delete ALL entries? (yes/no): "
                )

                if confirm.lower() != "yes":
                    print("Operation cancelled.")
                    return False

                # Delete all entries
                cur.execute("DELETE FROM hall_of_fame_entries")
                deleted_count = cur.rowcount

                # Reset the auto-increment sequence
                cur.execute("ALTER SEQUENCE hall_of_fame_entries_id_seq RESTART WITH 1")

                conn.commit()

                print(f"Successfully deleted {deleted_count} entries.")
                print(
                    "Database is now empty and ready for fresh data with correct chronological order."
                )
                return True

    except Exception as e:
        print(f"Database operation failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("Creole Creamery Database Cleaner")
    print("=" * 40)
    print("This script will clear all entries from the hall_of_fame_entries table.")
    print(
        "After clearing, you can run the scraper again to get the correct chronological order."
    )
    print()

    success = clear_database()

    if success:
        print()
        print("Next steps:")
        print("1. Run the scraper again: python test_scraper.py")
        print("2. Or deploy and trigger the Lambda function")
        print("3. The entries will now be inserted in correct chronological order")
    else:
        print()
        print(
            "Database clearing failed. Please check your configuration and try again."
        )
