"""Sugar Protocol CLI — command-line entry point for pipeline operations."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from db.database import Database
from pipeline.entity_registry import EntityRegistry
from pipeline.orchestrator import process_url, PipelineResult


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def _init_services() -> tuple[Database, EntityRegistry]:
    db = Database()
    await db.init()
    registry = EntityRegistry(db)
    return db, registry


# ═══════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════

async def cmd_analyze(url: str, verbose: bool = False) -> None:
    """Analyze a single URL through the full pipeline."""
    _setup_logging(verbose)
    db, registry = await _init_services()

    try:
        result = await process_url(url=url, db=db, registry=registry)
        _print_result(result)
    finally:
        await db.close()


async def cmd_batch(file_path: str, verbose: bool = False) -> None:
    """Batch-analyze URLs from a file (one URL per line)."""
    _setup_logging(verbose)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if not urls:
        print("No URLs found in file.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(urls)} URLs to process.\n")
    db, registry = await _init_services()

    succeeded = 0
    failed = 0
    try:
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] {url}")
            try:
                result = await process_url(url=url, db=db, registry=registry)
                _print_result_compact(result)
                succeeded += 1
            except Exception as e:
                print(f"  FAILED: {e}\n")
                failed += 1
    finally:
        await db.close()

    print(f"\nDone: {succeeded} succeeded, {failed} failed out of {len(urls)} total.")


async def cmd_entities_list(tier: str | None = None, verbose: bool = False) -> None:
    """List all entities in the registry."""
    _setup_logging(verbose)
    from interfaces import EntityTier

    db, registry = await _init_services()

    try:
        tier_filter = None
        if tier:
            try:
                tier_filter = EntityTier(tier.lower())
            except ValueError:
                valid = ", ".join(t.value for t in EntityTier)
                print(f"Error: invalid tier '{tier}'. Valid: {valid}", file=sys.stderr)
                sys.exit(1)

        entities = await registry.list_all(tier=tier_filter)

        if not entities:
            print("No entities found.")
            return

        # Table header
        print(f"{'ID':<20} {'Label':<20} {'Tier':<14} {'Aliases'}")
        print("-" * 74)
        for e in entities:
            aliases_str = ", ".join(e.aliases[:3]) if e.aliases else ""
            if e.aliases and len(e.aliases) > 3:
                aliases_str += f" (+{len(e.aliases) - 3})"
            print(f"{e.canonical_id:<20} {e.label:<20} {e.tier.value:<14} {aliases_str}")

        print(f"\nTotal: {len(entities)} entities")
    finally:
        await db.close()


# ═══════════════════════════════════════════
# Output formatting
# ═══════════════════════════════════════════

def _print_result(result: PipelineResult) -> None:
    """Print full analysis result."""
    print(f"\n{'=' * 60}")
    print(f"  {result.title}")
    print(f"{'=' * 60}")
    print(f"  URL:       {result.url}")
    print(f"  Type:      {result.article_type}")
    print(f"  Depth:     {result.analysis_depth}")
    print(f"  Tokens:    {result.token_usage.get('total_tokens', 0)}")
    print(f"  Cost:      ${result.cost:.4f}")

    if result.entities:
        print(f"\n  Entities ({len(result.entities)}):")
        for e in result.entities:
            print(f"    - {e.canonical_id} ({e.label}) [{e.match_type}]")

    if result.claims:
        print(f"\n  Claims ({len(result.claims)}):")
        for i, c in enumerate(result.claims):
            market = " [MARKET]" if c.potential_market else ""
            print(f"    {i+1}. [{c.claim_type.value}] {c.text}{market}")

    if result.edges:
        print(f"\n  Edges ({len(result.edges)}):")
        for e in result.edges:
            print(f"    - {e.source_id} --{e.edge_type.value}--> {e.target_id}")

    print()


def _print_result_compact(result: PipelineResult) -> None:
    """Print compact one-line summary for batch mode."""
    print(
        f"  OK: {result.article_type} | "
        f"{len(result.entities)} entities, "
        f"{len(result.claims)} claims | "
        f"${result.cost:.4f}\n"
    )


# ═══════════════════════════════════════════
# Argument parser
# ═══════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sugar",
        description="Sugar Protocol — Discourse Genealogy Pipeline",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze a single URL")
    p_analyze.add_argument("url", help="Article URL to analyze")

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch-analyze URLs from a file")
    p_batch.add_argument("file", help="Text file with one URL per line")

    # entities
    p_entities = subparsers.add_parser("entities", help="Entity registry operations")
    entities_sub = p_entities.add_subparsers(dest="entities_command")

    p_list = entities_sub.add_parser("list", help="List all entities")
    p_list.add_argument("--tier", help="Filter by tier (country, person, organization, ...)")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    verbose = args.verbose

    if args.command == "analyze":
        asyncio.run(cmd_analyze(args.url, verbose))

    elif args.command == "batch":
        asyncio.run(cmd_batch(args.file, verbose))

    elif args.command == "entities":
        if not args.entities_command:
            print("Usage: sugar entities list [--tier TIER]", file=sys.stderr)
            sys.exit(1)
        if args.entities_command == "list":
            asyncio.run(cmd_entities_list(tier=args.tier, verbose=verbose))


if __name__ == "__main__":
    main()
