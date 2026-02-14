"""
Database Migration: Standardize all enum columns to lowercase values.

This script updates all enum columns in the database to use lowercase values,
matching the standardized Python enums (ENUM_NAME = "lowercase_value").

Handles both native PostgreSQL enum types and VARCHAR columns by casting to TEXT.

Usage:
    # Dry run (default) - shows what would change
    python scripts/migrate_enums_to_lowercase.py

    # Commit changes
    python scripts/migrate_enums_to_lowercase.py --commit
"""
import os
import sys
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.database import SessionLocal
from sqlalchemy import text


# All enum columns that need migration: (table, column)
ENUM_COLUMNS = [
    ("conversations", "stage"),
    ("conversations", "intent_level"),
    ("conversations", "mode"),
    ("conversations", "user_sentiment"),
    ("leads", "conversation_stage"),
    ("leads", "intent_level"),
    ("leads", "user_sentiment"),
    ("messages", "message_from"),
    ("templates", "status"),
]


def show_current_values(db):
    """Display all distinct values for each enum column."""
    print("\n📊 Current distinct values in database:")
    print("=" * 60)
    for table, column in ENUM_COLUMNS:
        result = db.execute(
            text(f"SELECT CAST({column} AS TEXT) as val, COUNT(*) as cnt FROM {table} WHERE {column} IS NOT NULL GROUP BY val ORDER BY val")
        ).fetchall()
        if result:
            print(f"\n  {table}.{column}:")
            for value, count in result:
                needs_fix = value != value.lower()
                marker = " ⚠️  UPPERCASE" if needs_fix else " ✅"
                print(f"    '{value}' → {count} rows{marker}")
        else:
            print(f"\n  {table}.{column}: (no data)")


def migrate(db, commit: bool):
    """Run the migration to lowercase all enum values."""
    print("\n🔄 Migrating enum values to lowercase...")
    print("=" * 60)

    total_updated = 0

    for table, column in ENUM_COLUMNS:
        # Count rows that need updating (value != lowercase value)
        # Cast to TEXT to handle native PostgreSQL enum types
        count_result = db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL AND CAST({column} AS TEXT) != LOWER(CAST({column} AS TEXT))")
        ).scalar()

        if count_result > 0:
            print(f"  {table}.{column}: {count_result} rows to update")
            total_updated += count_result

            if commit:
                # Step 1: Drop the column's enum type constraint by altering to VARCHAR
                # Step 2: Update values to lowercase
                # Since the new code uses native_enum=False (VARCHAR), we convert the column
                db.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR USING CAST({column} AS TEXT)")
                )
                db.execute(
                    text(f"UPDATE {table} SET {column} = LOWER({column}) WHERE {column} IS NOT NULL AND {column} != LOWER({column})")
                )
        else:
            print(f"  {table}.{column}: ✅ already lowercase")

    if commit:
        # Clean up: drop orphaned enum types that are no longer used
        print("\n🧹 Cleaning up orphaned native enum types...")
        enum_types_to_drop = [
            "conversationstage", "intentlevel", "conversationmode",
            "usersentiment", "templatestatus", "messagefrom",
        ]
        for enum_type in enum_types_to_drop:
            try:
                db.execute(text(f"DROP TYPE IF EXISTS {enum_type} CASCADE"))
                print(f"  Dropped type: {enum_type}")
            except Exception as e:
                print(f"  Could not drop {enum_type}: {e}")

        db.commit()
        print(f"\n✅ Migration committed. {total_updated} rows updated.")
    else:
        print(f"\n⏸️  DRY RUN complete. {total_updated} rows would be updated.")
        print("   Run with --commit to apply changes.")

    return total_updated


def main():
    parser = argparse.ArgumentParser(description="Migrate enum values to lowercase")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually commit the changes (default is dry-run)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("🔍 Enum Migration: UPPERCASE → lowercase")
        print("=" * 60)
        print(f"Mode: {'COMMIT' if args.commit else 'DRY RUN'}")

        # Show before state
        show_current_values(db)

        # Run migration
        migrate(db, commit=args.commit)

        # Show after state (only if committed)
        if args.commit:
            show_current_values(db)

    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
