-- Migration 001: Add parsing columns
-- This migration adds new columns for parsed name data

-- Step 1: Add new columns (safe, non-destructive)
ALTER TABLE hall_of_fame_entries
ADD COLUMN IF NOT EXISTS notes VARCHAR(255),
ADD COLUMN IF NOT EXISTS age INTEGER,
ADD COLUMN IF NOT EXISTS elapsed_time INTEGER,
ADD COLUMN IF NOT EXISTS completion_count INTEGER;

-- Step 2: Add comments for documentation
COMMENT ON COLUMN hall_of_fame_entries.notes IS 'Raw extracted notes from name parsing';
COMMENT ON COLUMN hall_of_fame_entries.age IS 'Age in total days';
COMMENT ON COLUMN hall_of_fame_entries.elapsed_time IS 'Time in seconds to complete challenge';
COMMENT ON COLUMN hall_of_fame_entries.completion_count IS 'Completion number from notes (1st, 2nd, 3rd, etc.)';

-- Step 3: Create backup of original names (for rollback)
ALTER TABLE hall_of_fame_entries
ADD COLUMN IF NOT EXISTS original_name VARCHAR(255);

-- Copy current names to backup column
UPDATE hall_of_fame_entries
SET original_name = name
WHERE original_name IS NULL;
