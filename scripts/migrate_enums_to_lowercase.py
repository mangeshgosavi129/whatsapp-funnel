"""
Database Migration: Standardize all enum columns to lowercase values.

This script updates all VARCHAR enum columns in the database to use lowercase values,
matching the standardized Python enums (ENUM_NAME = "lowercase_value").

Since the database uses native_enum=False (VARCHAR columns), this is a simple
UPDATE ... SET col = LOWER(col) operation with no schema changes needed.

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
            text(f"SELECT {column}, COUNT(*) as cnt FROM {table} WHERE {column} IS NOT NULL GROUP BY {column} ORDER BY {column}")
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
        count_result = db.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NOT NULL AND {column} != LOWER({column})")
        ).scalar()

        if count_result > 0:
            print(f"  {table}.{column}: {count_result} rows to update")

            if commit:
                db.execute(
                    text(f"UPDATE {table} SET {column} = LOWER({column}) WHERE {column} IS NOT NULL AND {column} != LOWER({column})")
                )
                total_updated += count_result
        else:
            print(f"  {table}.{column}: ✅ already lowercase")

    if commit:
        db.commit()
        print(f"\n✅ Migration committed. {total_updated} rows updated.")
    else:
        print(f"\n⏸️  DRY RUN complete. {total_updated + sum(1 for _ in [])} rows would be updated.")
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
