"""
Diff service — generates diffs between old and new document text.

Uses Python's built-in difflib for unified diff generation,
HTML side-by-side diff, and change statistics.
"""

import difflib

from app.schemas.revision import DiffResult, DiffStats


class DiffService:
    """Generates structured diffs between two text versions."""

    def generate_diff(self, old_text: str, new_text: str) -> DiffResult:
        """Generate unified diff, HTML diff, and change statistics.

        Args:
            old_text: Original document text.
            new_text: New document text after revision.

        Returns:
            DiffResult with unified_diff, html_diff, and stats.
        """
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        # Unified diff
        unified = "".join(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old",
            tofile="new",
            n=3,
        ))

        # HTML side-by-side diff
        html_diff_obj = difflib.HtmlDiff(tabsize=2)
        html_diff = html_diff_obj.make_table(
            old_lines,
            new_lines,
            context=True,
            numlines=3,
        )

        # Statistics
        stats = self._compute_stats(old_lines, new_lines)

        return DiffResult(
            unified_diff=unified,
            html_diff=html_diff,
            stats=stats,
        )

    def _compute_stats(self, old_lines: list[str], new_lines: list[str]) -> DiffStats:
        """Count added, removed, and changed lines using SequenceMatcher.

        Uses difflib.SequenceMatcher for accurate line-level change detection.
        """
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        added = 0
        removed = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                removed += i2 - i1
                added += j2 - j1
            elif tag == "delete":
                removed += i2 - i1
            elif tag == "insert":
                added += j2 - j1

        changed = min(added, removed)
        return DiffStats(
            added=added - changed,
            removed=removed - changed,
            changed=changed,
        )

    def is_unchanged(self, old_text: str, new_text: str) -> bool:
        """Check if text is effectively unchanged (ignoring leading/trailing whitespace)."""
        return old_text.strip() == new_text.strip()


# Singleton
diff_service = DiffService()
