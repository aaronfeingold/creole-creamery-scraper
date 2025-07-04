# Database Migration Guide

This guide explains how to safely migrate existing database data by adding new columns and transforming existing data to populate them.

## Migration Files

- `migration_001_add_parsing_columns.sql` - Adds new columns to the database
- `migrate_date_migration_001.py` - Python script to transform existing data and populate new columns
- `cleanup_migration_001.sql` - Optional cleanup script to remove backup columns

## Migration Process

### Step 1: Preview the Migration (Safe)

First, preview what the migration would do without making any changes:

```bash
python migrate_date_migration_001.py preview
```

This will show you sample records and how they would be transformed.

### Step 2: Run the SQL Migration

Add the new columns to your database:

```bash
psql $DATABASE_URL -f migration_001_add_parsing_columns.sql
```

This will:

- Add new columns for the parsed/extracted data
- Add backup columns to preserve original data
- Copy current data to backup columns for safety

### Step 3: Run the Data Migration

Transform existing data and populate the new columns:

```bash
python migrate_date_migration_001.py migrate
```

This will:

- Process all existing records through your transformation logic
- Extract structured data from existing fields
- Clean up original fields by removing extracted information
- Populate the new columns with parsed data

### Step 4: Verify the Migration

Check that the migration worked correctly:

```bash
python migrate_date_migration_001.py verify
```

This will show:

- Statistics about the transformation results
- Examples of transformed records
- Comparison with original data

### Step 5: Rollback if Needed

If something went wrong, you can rollback:

```bash
python migrate_date_migration_001.py rollback
```

This will restore the original data and clear the new columns.

### Step 6: Optional Cleanup

After confirming the migration worked correctly, you can optionally remove backup columns:

```bash
psql $DATABASE_URL -f cleanup_migration_001.sql
```

## Example: Data Transformation Patterns

The migration extracts structured data from existing fields. Here are some common patterns:

### Pattern Extraction

- `PHILLIP YERO, 2ND TIME` → name: `PHILLIP YERO`, completion_count: `2`
- `SOMEONE, 3RD TIME` → name: `SOMEONE`, completion_count: `3`

### Age Information

- `JILL SMITH 11 YEARS 5 MONTHS 21 DAYS` → name: `JILL SMITH`, age: `4186` (total days)
- `TOM DAVIS 15 YEARS` → name: `TOM DAVIS`, age: `5475` (total days)

### Time Information

- `STEVEN HAMMOND 7 MINUTES` → name: `STEVEN HAMMOND`, elapsed_time: `420` (total seconds)
- `JOHN VALDESPINO 6 MINUTES 40 SECONDS` → name: `JOHN VALDESPINO`, elapsed_time: `400` (total seconds)

### Clean Data

- `JANE SMITH` → name: `JANE SMITH` (no changes, all other fields null)

## Environment Variables

Make sure your database connection string is set before running the migration:

```bash
export NEON_DATABASE_URL="your-database-url"
```

## Safety Features

1. **Backup Columns**: Original data is preserved in backup columns
2. **Preview Mode**: See what would happen without making changes
3. **Rollback**: Easily undo the migration if needed
4. **Verification**: Check results before proceeding
5. **Idempotent**: Safe to run multiple times (won't re-process already migrated records)

## After Migration

Once the migration is complete, your application can use the new structured data for better queries and analysis. For example:

```sql
-- Example query using the new structured data
WITH completion_stats AS (
  SELECT name, COUNT(*) as actual_entries,
         MAX(COALESCE(completion_count, 1)) as max_implied_count
  FROM your_table GROUP BY name
)
SELECT name, GREATEST(actual_entries, max_implied_count) as count
FROM completion_stats
WHERE GREATEST(actual_entries, max_implied_count) >= 2
ORDER BY count DESC;
```

This pattern allows you to work with structured data instead of parsing strings at query time.

## Customizing for Your Migration

To adapt this guide for your specific migration:

1. Update the file names to match your migration files
2. Modify the transformation examples to match your data patterns
3. Adjust the SQL queries to work with your table structure
4. Update the environment variable name if needed
5. Customize the verification queries for your specific use case
