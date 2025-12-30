"""CLI script for reviewing and revising newsletter digests."""

import argparse
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.models.digest import DigestStatus
from src.services.review_service import ReviewService
from src.utils.digest_formatter import DigestFormatter
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def list_pending_reviews() -> None:
    """Display all digests pending review (CLI presentation)."""
    service = ReviewService()
    digests = await service.list_pending_reviews()

    if not digests:
        print("\nNo digests pending review.\n")
        return

    print("\n" + "=" * 100)
    print(f"DIGESTS PENDING REVIEW ({len(digests)} total)")
    print("=" * 100)
    print(
        f"\n{'ID':<6} {'Type':<8} {'Period':<24} {'Created':<20} {'Newsletters':<12} {'Revisions':<10}"
    )
    print("-" * 100)

    for digest in digests:
        period = (
            f"{digest.period_start.strftime('%Y-%m-%d')} to "
            f"{digest.period_end.strftime('%Y-%m-%d')}"
        )
        created = digest.created_at.strftime("%Y-%m-%d %H:%M")

        print(
            f"{digest.id:<6} {digest.digest_type:<8} {period:<24} "
            f"{created:<20} {digest.newsletter_count:<12} {digest.revision_count:<10}"
        )

    print("\n")


async def view_digest(digest_id: int, format: str = "markdown") -> Optional[Any]:
    """Display digest content for review.

    Args:
        digest_id: Digest ID to view
        format: Output format (markdown, html, text)

    Returns:
        Digest object if found, None otherwise
    """
    service = ReviewService()
    digest = await service.get_digest(digest_id)

    if not digest:
        print(f"\nError: Digest {digest_id} not found.\n")
        return None

    print("\n" + "=" * 80)
    print(f"DIGEST #{digest_id}")
    print("=" * 80)
    print(f"\nType: {digest.digest_type}")
    print(
        f"Period: {digest.period_start.strftime('%Y-%m-%d')} to "
        f"{digest.period_end.strftime('%Y-%m-%d')}"
    )
    print(f"Status: {digest.status}")
    print(f"Newsletters: {digest.newsletter_count}")
    print(f"Revisions: {digest.revision_count}")

    if digest.reviewed_by:
        print(f"Reviewed by: {digest.reviewed_by}")
        print(f"Reviewed at: {digest.reviewed_at.strftime('%Y-%m-%d %H:%M')}")

    print("\n" + "=" * 80)
    print("CONTENT")
    print("=" * 80 + "\n")

    # Format digest
    formatter = DigestFormatter()
    if format == "markdown":
        output = formatter.to_markdown(digest)
    elif format == "html":
        output = formatter.to_html(digest)
    else:
        output = formatter.to_plain_text(digest)

    print(output)
    print("\n")

    return digest


async def interactive_revision_session(
    digest_id: int,
    reviewer: Optional[str] = None,
) -> Any:
    """Multi-turn conversational revision session (CLI interaction).

    Args:
        digest_id: Digest ID to revise
        reviewer: Reviewer name/email (optional)

    Returns:
        Final digest after revisions
    """
    service = ReviewService()

    # 1. Load context via service
    session_id = str(uuid.uuid4())

    try:
        context = await service.start_revision_session(
            digest_id,
            session_id,
            reviewer or "cli-user",
        )
    except ValueError as e:
        print(f"\nError: {e}\n")
        return None

    # 2. Initialize session tracking
    session = {
        "session_id": session_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": reviewer or "cli-user",
        "turns": [],
        "final_action": None,
    }

    # 3. Display initial digest
    print("\n" + "=" * 80)
    print("CURRENT DIGEST")
    print("=" * 80 + "\n")

    formatter = DigestFormatter()
    print(formatter.to_markdown(context.digest))

    # 4. Interactive loop
    print("\n" + "=" * 80)
    print("AI REVISION ASSISTANT")
    print("=" * 80)
    print("Commands:")
    print("  - Type your revision request (e.g., 'Make executive summary more concise')")
    print("  - 'show' to redisplay current digest")
    print("  - 'done' to finish and review changes")
    print("  - 'cancel' to abort without saving")
    print("\n")

    turn_number = 0
    working_digest = context.digest
    conversation_history: List[Dict[str, Any]] = []

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "cancel":
            print("\nRevision cancelled. No changes saved.\n")
            return await service.get_digest(digest_id)

        if user_input.lower() == "done":
            break

        if user_input.lower() == "show":
            print("\n" + "=" * 80)
            print("CURRENT DIGEST (WITH CHANGES)")
            print("=" * 80 + "\n")
            print(formatter.to_markdown(working_digest))
            continue

        # Process revision request via service
        turn_number += 1
        print("\nAI: [Analyzing request with full context...]")

        try:
            result = await service.process_revision_turn(
                context=context,
                user_input=user_input,
                conversation_history=conversation_history,
                session_id=session_id,
            )
        except Exception as e:
            print(f"\nError processing revision: {e}")
            print("Please try again or type 'cancel' to abort.\n")
            continue

        # Display proposed changes
        print(f"\nAI: {result.explanation}\n")
        print("=" * 80)
        print(f"PROPOSED CHANGE TO: {result.section_modified}")
        print("=" * 80)

        # Format the revised content nicely
        if isinstance(result.revised_content, list):
            for idx, item in enumerate(result.revised_content, 1):
                if isinstance(item, dict):
                    print(f"\n{idx}. {item.get('title', 'Untitled')}")
                    print(f"   {item.get('summary', '')}")
                else:
                    print(f"{idx}. {item}")
        elif isinstance(result.revised_content, dict):
            for key, value in result.revised_content.items():
                print(f"\n{key}:")
                if isinstance(value, list):
                    for item in value:
                        print(f"  - {item}")
                else:
                    print(f"  {value}")
        else:
            print(result.revised_content)

        print("=" * 80)

        # Get approval
        keep = input("\nKeep this change? [yes/no/edit]: ").strip().lower()

        if keep == "yes":
            # Apply revision via service
            try:
                working_digest = await service.apply_revision(
                    digest_id=digest_id,
                    section=result.section_modified,
                    new_content=result.revised_content,
                    increment_count=True,
                )
                # Reload context with updated digest
                context.digest = working_digest

                change_accepted = True
                print("✓ Change applied\n")
            except Exception as e:
                print(f"\nError applying revision: {e}")
                print("Change not applied. Continuing with previous version.\n")
                change_accepted = False
        else:
            change_accepted = False
            print("✗ Change discarded\n")

        # Track turn for audit trail
        turn = await service.create_revision_turn(
            turn_number=turn_number,
            user_input=user_input,
            ai_response=result.explanation,
            section_modified=result.section_modified,
            change_accepted=change_accepted,
            tools_called=result.tools_used,
        )
        session["turns"].append(turn.to_dict())

        # Update conversation history for next turn (Anthropic SDK format)
        # This is simplified - in production, would need full message format
        conversation_history.append(
            {
                "role": "user",
                "content": user_input,
            }
        )
        conversation_history.append(
            {
                "role": "assistant",
                "content": result.explanation,
            }
        )

    # 5. Session complete
    session["ended_at"] = datetime.now(timezone.utc).isoformat()

    # 6. Final review
    print("\n" + "=" * 80)
    print("REVISED DIGEST (FINAL)")
    print("=" * 80 + "\n")
    print(formatter.to_markdown(working_digest))

    # Show cost summary
    cost = service.calculate_revision_cost()
    print("\n" + "=" * 80)
    print(f"Session Summary:")
    print(f"  - Turns: {turn_number}")
    print(f"  - Changes Applied: {working_digest.revision_count}")
    print(f"  - Estimated Cost: ${cost:.4f}")
    print("=" * 80 + "\n")

    action = input("Action [approve/save-draft/discard]: ").strip().lower()

    valid_actions = ["approve", "save-draft", "discard"]
    while action not in valid_actions:
        print(f"Invalid action. Choose: {', '.join(valid_actions)}")
        action = input("Action [approve/save-draft/discard]: ").strip().lower()

    session["final_action"] = action

    # 7. Finalize review via service
    if action == "discard":
        print("\nRevision discarded. Returning to original digest.\n")
        return await service.get_digest(digest_id)

    # Build revision history
    revision_history = {"sessions": [session]}

    # Finalize through service
    try:
        final_digest = await service.finalize_review(
            digest_id=digest_id,
            action=action,
            revision_history=revision_history,
            reviewer=reviewer or "cli-user",
        )

        print(f"\n✓ Digest #{digest_id} {action}d successfully")
        print(f"  Status: {final_digest.status}")
        print(f"  Revision Count: {final_digest.revision_count}")
        print(f"  Reviewed By: {final_digest.reviewed_by}")
        print()

        return final_digest

    except Exception as e:
        print(f"\nError finalizing review: {e}\n")
        return working_digest


async def quick_review(
    digest_id: int,
    action: str,
    notes: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> bool:
    """Quick approve/reject without revision (batch mode).

    Args:
        digest_id: Digest ID
        action: 'approve' or 'reject'
        notes: Optional review notes
        reviewer: Reviewer name/email

    Returns:
        True if successful, False otherwise
    """
    service = ReviewService()

    try:
        digest = await service.quick_review(
            digest_id=digest_id,
            action=action,
            reviewer=reviewer or "cli-user",
            notes=notes,
        )

        print(f"\n✓ Digest #{digest_id} {action}d successfully")
        print(f"  Status: {digest.status}")
        print(f"  Reviewed By: {digest.reviewed_by}")
        print()

        return True

    except ValueError as e:
        print(f"\nError: {e}\n")
        return False
    except Exception as e:
        print(f"\nError during review: {e}\n")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Review and revise newsletter digests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all digests pending review
  python -m scripts.review_digest --list

  # View specific digest
  python -m scripts.review_digest --id 42 --view

  # Interactive revision session
  python -m scripts.review_digest --id 42 --revise-interactive

  # Quick approve
  python -m scripts.review_digest --id 42 --action approve

  # Quick reject with notes
  python -m scripts.review_digest --id 42 --action reject --notes "Too technical for exec audience"
        """,
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--list",
        action="store_true",
        help="List all digests pending review",
    )
    mode_group.add_argument(
        "--id",
        type=int,
        help="Digest ID to review",
    )

    # Review modes (when --id is specified)
    parser.add_argument(
        "--revise-interactive",
        action="store_true",
        help="Start interactive revision session with AI",
    )
    parser.add_argument(
        "--action",
        choices=["approve", "reject"],
        help="Quick review action (no revision)",
    )
    parser.add_argument(
        "--notes",
        type=str,
        help="Review notes (for quick review)",
    )
    parser.add_argument(
        "--reviewer",
        type=str,
        help="Reviewer name/email",
    )

    # Display options
    parser.add_argument(
        "--format",
        choices=["markdown", "html", "text"],
        default="markdown",
        help="Output format for digest display",
    )
    parser.add_argument(
        "--view",
        action="store_true",
        help="Just view digest (no action)",
    )

    args = parser.parse_args()

    # Route to handlers
    if args.list:
        asyncio.run(list_pending_reviews())

    elif args.id:
        if args.revise_interactive:
            # Interactive AI revision session
            asyncio.run(interactive_revision_session(args.id, args.reviewer))

        elif args.action:
            # Quick batch approve/reject
            asyncio.run(quick_review(args.id, args.action, args.notes, args.reviewer))

        elif args.view:
            # Just display
            asyncio.run(view_digest(args.id, args.format))

        else:
            # Default: view digest and show available actions
            digest = asyncio.run(view_digest(args.id, args.format))
            if digest:
                print("Available actions:")
                print(f"  --revise-interactive  : Start interactive AI revision")
                print(f"  --action approve      : Quick approve")
                print(f"  --action reject       : Quick reject")
                print()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
