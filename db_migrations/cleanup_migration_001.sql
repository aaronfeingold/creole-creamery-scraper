-- Cleanup Migration_001: Remove backup column after successful migration_001
-- ONLY run this after verifying the migration_001 was successful

-- Optional: Remove the backup column to save space
-- Uncomment the line below ONLY if you're confident the migration_001 worked correctly
-- ALTER TABLE hall_of_fame_entries DROP COLUMN original_name;

-- Check migration_001 statistics before cleanup
SELECT
    COUNT(*) as total_records,
    COUNT(notes) as records_with_notes,
    COUNT(age) as records_with_age,
    COUNT(elapsed_time) as records_with_time,
    COUNT(completion_count) as records_with_completion
FROM hall_of_fame_entries;

-- Show examples of parsed data from migration_001
SELECT name, notes, age, elapsed_time, completion_count
FROM hall_of_fame_entries
WHERE notes IS NOT NULL OR age IS NOT NULL OR elapsed_time IS NOT NULL OR completion_count IS NOT NULL
LIMIT 50;
