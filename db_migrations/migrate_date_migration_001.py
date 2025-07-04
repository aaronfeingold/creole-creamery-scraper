import psycopg2
import re
import os
from typing import Optional, Tuple


def _normalize_age_to_days(age_text: str) -> Optional[int]:
    """Convert age text like '11 YEARS 5 MONTHS 21 DAYS' or '10 YRS OLD' to total days."""
    try:
        total_days = 0
        years_match = re.search(r"(\d+)\s+(?:YEARS?|YRS?)", age_text)
        if years_match:
            total_days += int(years_match.group(1)) * 365
        months_match = re.search(r"(\d+)\s+MONTHS?", age_text)
        if months_match:
            total_days += int(months_match.group(1)) * 30
        days_match = re.search(r"(\d+)\s+DAYS?", age_text)
        if days_match:
            total_days += int(days_match.group(1))
        return total_days if total_days > 0 else None
    except (ValueError, AttributeError):
        return None


def _normalize_time_to_seconds(time_text: str) -> Optional[int]:
    """Convert time text like '6 MINUTES 40 SECONDS' to total seconds."""
    try:
        total_seconds = 0
        minutes_match = re.search(r"(\d+)\s+MINUTES?", time_text)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60
        seconds_match = re.search(r"(\d+)\s+SECONDS?", time_text)
        if seconds_match:
            total_seconds += int(seconds_match.group(1))
        return total_seconds if total_seconds > 0 else None
    except (ValueError, AttributeError):
        return None


def _extract_completion_count(notes_text: str) -> Optional[int]:
    """Extract completion count from notes like '2ND TIME', '3RD TIME', etc."""
    if not notes_text:
        return None
    try:
        match = re.search(r"(\d+)(ST|ND|RD|TH)\s+TIME", notes_text.upper())
        if match:
            return int(match.group(1))
        return None
    except (ValueError, AttributeError):
        return None


def parse_name_and_notes(
    raw_name: str,
) -> Tuple[str, Optional[str], Optional[int], Optional[int], Optional[int]]:
    """Parse existing name field and extract notes, age, time, completion count."""
    cleaned = raw_name.strip().upper()

    # Check for comma-separated patterns (completion count, etc.)
    if "," in cleaned:
        parts = cleaned.split(",", 1)
        name_part = parts[0].strip()
        potential_note = parts[1].strip()

        # Completion count patterns: "2nd time", "3rd time", etc.
        if re.match(r"^\d+(ST|ND|RD|TH)\s+TIME$", potential_note):
            completion_count = _extract_completion_count(potential_note)
            return name_part, potential_note, None, None, completion_count

        return cleaned, None, None, None, None

    # Check for patterns at the end of the name (no comma)

    # Age pattern: "11 YEARS 5 MONTHS 21 DAYS" or "10 YRS OLD"
    age_match = re.search(
        r"\s+(\d+\s+(?:YEARS?|YRS?)(?:\s+\d+\s+MONTHS?)?(?:\s+\d+\s+DAYS?)?(?:\s+OLD)?)$",
        cleaned,
    )
    if age_match:
        note = age_match.group(1)
        name = cleaned[: age_match.start()].strip()
        age_days = _normalize_age_to_days(note)
        return name, note, age_days, None, None

    # Time patterns: "7 MINUTES" or "6 MINUTES 40 SECONDS"
    time_match = re.search(r"\s+(\d+\s+MINUTES?(?:\s+\d+\s+SECONDS?)?)$", cleaned)
    if time_match:
        note = time_match.group(1)
        name = cleaned[: time_match.start()].strip()
        elapsed_seconds = _normalize_time_to_seconds(note)
        return name, note, None, elapsed_seconds, None

    # No patterns found, return the whole name
    return cleaned, None, None, None, None


def migrate_migration_001_data():
    """Migrate existing data for migration_001 by parsing names and updating new columns."""
    print("Starting migration_001 data migration...")
    print("This will parse existing name data and populate the new parsing columns.")

    db_url = os.environ.get("NEON_DATABASE_URL")
    if not db_url:
        print("Error: NEON_DATABASE_URL environment variable not set")
        return

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Get all existing records that haven't been migrated yet
                cur.execute(
                    """
                    SELECT id, name, original_name
                    FROM hall_of_fame_entries
                    WHERE notes IS NULL AND age IS NULL AND elapsed_time IS NULL AND completion_count IS NULL
                """
                )

                records = cur.fetchall()
                print(f"Found {len(records)} records to migrate for migration_001")

                updated_count = 0

                for record_id, current_name, original_name in records:
                    # Use original_name if available, otherwise current name
                    name_to_parse = original_name if original_name else current_name

                    # Parse the name
                    clean_name, notes, age_days, elapsed_seconds, completion_count = (
                        parse_name_and_notes(name_to_parse)
                    )

                    # Update the record with migration_001 columns
                    cur.execute(
                        """
                        UPDATE hall_of_fame_entries
                        SET name = %s, notes = %s, age = %s, elapsed_time = %s, completion_count = %s
                        WHERE id = %s
                    """,
                        (
                            clean_name,
                            notes,
                            age_days,
                            elapsed_seconds,
                            completion_count,
                            record_id,
                        ),
                    )

                    if notes or age_days or elapsed_seconds or completion_count:
                        updated_count += 1
                        print(
                            f"Updated: '{name_to_parse}' -> name: '{clean_name}', "
                            f"notes: {notes}, age: {age_days}, time: {elapsed_seconds}, count: {completion_count}"
                        )

                conn.commit()
                print("\nMigration_001 data migration completed successfully!")
                print(f"Total records processed: {len(records)}")
                print(f"Records with extracted data: {updated_count}")

    except Exception as e:
        print(f"Migration_001 data migration failed: {str(e)}")
        raise


def verify_migration_001():
    """Verify the migration_001 data migration worked correctly."""
    print("Verifying migration_001 data migration...")

    db_url = os.environ.get("NEON_DATABASE_URL")

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Check some statistics
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_records,
                        COUNT(notes) as records_with_notes,
                        COUNT(age) as records_with_age,
                        COUNT(elapsed_time) as records_with_time,
                        COUNT(completion_count) as records_with_completion
                    FROM hall_of_fame_entries
                """
                )

                stats = cur.fetchone()
                print("Migration_001 Verification:")
                print(f"Total records: {stats[0]}")
                print(f"Records with notes: {stats[1]}")
                print(f"Records with age: {stats[2]}")
                print(f"Records with elapsed time: {stats[3]}")
                print(f"Records with completion count: {stats[4]}")

                # Show some examples
                cur.execute(
                    """
                    SELECT name, notes, age, elapsed_time, completion_count, original_name
                    FROM hall_of_fame_entries
                    WHERE notes IS NOT NULL OR age IS NOT NULL OR elapsed_time IS NOT NULL
                       OR completion_count IS NOT NULL
                    LIMIT 5
                """
                )

                examples = cur.fetchall()
                print("\nExamples of parsed data from migration_001:")
                for ex in examples:
                    print(
                        f"Name: '{ex[0]}', Notes: {ex[1]}, Age: {ex[2]}, "
                        f"Time: {ex[3]}, Count: {ex[4]}, Original: '{ex[5]}'"
                    )

    except Exception as e:
        print(f"Migration_001 verification failed: {str(e)}")


def rollback_migration_001():
    """Rollback the migration_001 data migration if needed."""
    print("Rolling back migration_001 data migration...")
    print("This will restore original names and clear the new parsing columns.")

    db_url = os.environ.get("NEON_DATABASE_URL")

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Restore original names and clear migration_001 columns
                cur.execute(
                    """
                    UPDATE hall_of_fame_entries
                    SET name = original_name, notes = NULL, age = NULL, elapsed_time = NULL, completion_count = NULL
                    WHERE original_name IS NOT NULL
                """
                )

                conn.commit()
                print("Migration_001 data migration rolled back successfully!")

    except Exception as e:
        print(f"Migration_001 rollback failed: {str(e)}")


def preview_migration_001():
    """Preview what the migration_001 data migration would do without making changes."""
    print("Previewing migration_001 data migration...")
    print("This shows what changes would be made without actually applying them.")

    db_url = os.environ.get("NEON_DATABASE_URL")

    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Get sample of existing records
                cur.execute(
                    """
                    SELECT id, name
                    FROM hall_of_fame_entries
                    LIMIT 10
                """
                )

                records = cur.fetchall()
                print("Preview of migration_001 data migration (first 10 records):")
                print("=" * 80)

                for record_id, current_name in records:
                    clean_name, notes, age_days, elapsed_seconds, completion_count = (
                        parse_name_and_notes(current_name)
                    )

                    print(f"ID: {record_id}")
                    print(f"  Original: '{current_name}'")
                    print(f"  New name: '{clean_name}'")
                    print(f"  Notes: {notes}")
                    print(f"  Age (days): {age_days}")
                    print(f"  Elapsed time (seconds): {elapsed_seconds}")
                    print(f"  Completion count: {completion_count}")
                    print()

    except Exception as e:
        print(f"Migration_001 preview failed: {str(e)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "preview":
            preview_migration_001()
        elif sys.argv[1] == "migrate":
            migrate_migration_001_data()
        elif sys.argv[1] == "verify":
            verify_migration_001()
        elif sys.argv[1] == "rollback":
            rollback_migration_001()
        else:
            print(
                "Usage: python migrate_migration_001_data.py [preview|migrate|verify|rollback]"
            )
    else:
        print(
            "Usage: python migrate_migration_001_data.py [preview|migrate|verify|rollback]"
        )
        print()
        print("Commands for migration_001 data migration:")
        print("  preview  - Show what the migration would do (safe)")
        print("  migrate  - Run the actual migration_001 data migration")
        print("  verify   - Check migration_001 results")
        print("  rollback - Undo the migration_001 data migration")
