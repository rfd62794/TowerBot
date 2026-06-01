"""CLI for database sync operations."""

import sys
import os
import argparse
import json

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from infra.db.sync import DBSync


def cmd_status(args):
    """Show table inventory and classification."""
    sync = DBSync()
    inventory = sync.get_table_inventory()
    
    print("📊 Database Sync Status")
    print("=" * 50)
    
    shared = [name for name, info in inventory.items() if info["policy"] == "shared"]
    instance = [name for name, info in inventory.items() if info["policy"] == "instance"]
    cache = [name for name, info in inventory.items() if info["policy"] == "cache"]
    config = [name for name, info in inventory.items() if info["policy"] == "config"]
    
    print(f"\n🔄 SHARED tables ({len(shared)}):")
    for table in shared:
        print(f"  {table}: {inventory[table]['row_count']} rows")
    
    print(f"\n🔒 INSTANCE tables ({len(instance)}):")
    for table in instance:
        print(f"  {table}: {inventory[table]['row_count']} rows")
    
    print(f"\n⏭️ CACHE tables ({len(cache)}):")
    for table in cache:
        print(f"  {table}: {inventory[table]['row_count']} rows")
    
    print(f"\n⚙️ CONFIG tables ({len(config)}):")
    for table in config:
        print(f"  {table}: {inventory[table]['row_count']} rows")
    
    print(f"\n📦 Total tables: {len(inventory)}")
    print(f"🔄 SHARED rows to sync: {sum(inventory[t]['row_count'] for t in shared)}")


def cmd_export(args):
    """Export SHARED tables to JSON."""
    sync = DBSync()
    
    tables = None
    if args.tables:
        tables = args.tables.split(",")
    
    output_path = args.output or "sync.json"
    
    print(f"📦 Exporting to {output_path}...")
    result_path = sync.export_tables(tables=tables, output_path=output_path)
    print(f"✅ Export complete: {result_path}")


def cmd_import(args):
    """Import tables from sync source."""
    sync = DBSync()
    
    source = args.source or "sync.json"
    dry_run = not args.apply
    conflict = args.conflict
    
    print(f"📥 Importing from {source}...")
    if dry_run:
        print("🔍 Dry-run mode — no changes will be applied")
    
    report = sync.import_tables(source=source, dry_run=dry_run, conflict=conflict)
    
    print(f"\n📊 Import Report:")
    print(f"  Added: {report['added']}")
    print(f"  Updated: {report['updated']}")
    print(f"  Conflicts: {report['conflicts']}")
    print(f"  Skipped: {report['skipped']}")
    
    if not dry_run:
        print(f"✅ Import complete")
    else:
        print(f"🔍 Dry-run complete — use --apply to apply changes")


def cmd_diff(args):
    """Compare local DB with sync source."""
    sync = DBSync()
    
    source = args.source or "sync.json"
    
    print(f"🔍 Comparing with {source}...")
    diff = sync.diff(source)
    
    print(f"\n📊 Diff Report:")
    
    if diff["only_local"]:
        print(f"\n  Only in local ({len(diff['only_local'])}):")
        for table in diff["only_local"]:
            print(f"    {table}")
    
    if diff["only_remote"]:
        print(f"\n  Only in remote ({len(diff['only_remote'])}):")
        for table in diff["only_remote"]:
            print(f"    {table}")
    
    if diff["differing"]:
        print(f"\n  Row count differences ({len(diff['differing'])}):")
        for item in diff["differing"]:
            print(f"    {item['table']}: local={item['local_count']}, remote={item['remote_count']}")
    
    if not any([diff["only_local"], diff["only_remote"], diff["differing"]]):
        print("  ✅ No differences found")


def main():
    parser = argparse.ArgumentParser(description="Database sync CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Show table inventory")
    status_parser.set_defaults(func=cmd_status)
    
    # export command
    export_parser = subparsers.add_parser("export", help="Export SHARED tables")
    export_parser.add_argument("--tables", help="Comma-separated list of tables to export")
    export_parser.add_argument("--output", help="Output file path (default: sync.json)")
    export_parser.set_defaults(func=cmd_export)
    
    # import command
    import_parser = subparsers.add_parser("import", help="Import tables from sync source")
    import_parser.add_argument("source", nargs="?", help="Source file path (default: sync.json)")
    import_parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    import_parser.add_argument("--conflict", help="Conflict resolution strategy")
    import_parser.set_defaults(func=cmd_import)
    
    # diff command
    diff_parser = subparsers.add_parser("diff", help="Compare local with sync source")
    diff_parser.add_argument("source", nargs="?", help="Source file path (default: sync.json)")
    diff_parser.set_defaults(func=cmd_diff)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
