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
        else:
            print(f"  {table}.{column}: ✅ already lowercase (or empty)")

    if commit:
        # Step 1: Convert ALL columns from native enum to VARCHAR first
        # This must happen before dropping types, otherwise CASCADE removes columns
        print("\n📐 Converting all enum columns to VARCHAR...")
        for table, column in ENUM_COLUMNS:
            try:
                db.execute(
                    text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR USING CAST({column} AS TEXT)")
                )
                print(f"  {table}.{column} → VARCHAR ✅")
            except Exception as e:
                # Column might already be VARCHAR
                db.rollback()
                print(f"  {table}.{column} → already VARCHAR (skipped)")

        # Step 2: Update values to lowercase
        print("\n📝 Lowercasing values...")
        for table, column in ENUM_COLUMNS:
            db.execute(
                text(f"UPDATE {table} SET {column} = LOWER({column}) WHERE {column} IS NOT NULL AND {column} != LOWER({column})")
            )

        # Step 3: Drop orphaned native enum types
        print("\n🧹 Cleaning up orphaned native enum types...")
        enum_types_to_drop = [
            "conversationstage", "intentlevel", "conversationmode",
            "usersentiment", "templatestatus", "messagefrom",
        ]
        for enum_type in enum_types_to_drop:
            try:
                db.execute(text(f"DROP TYPE IF EXISTS {enum_type}"))
                print(f"  Dropped type: {enum_type}")
            except Exception:
                print(f"  Type {enum_type} not found (already removed)")

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
