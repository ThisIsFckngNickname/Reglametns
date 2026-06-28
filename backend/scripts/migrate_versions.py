"""
Migration script: create version 1 for all existing documents without versions.

Phase 7 — Versioning:
- Creates DocumentVersion v1 for documents that don't have any versions
- Copies existing files to the new versioned path format:
    from: storage/{company_id}/{doc_id}/{filename}
    to:   storage/{company_id}/{doc_id}/v1/{filename}
- Computes file_hash for all version records
"""

import asyncio
import hashlib
import logging
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from app.database import async_session
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.document_version import DocumentVersion
from app.services.storage_service import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 50


async def migrate_documents():
    """Create version 1 for all documents without versions."""
    async with async_session() as db:
        # Find documents without versions
        stmt = (
            select(Document)
            .outerjoin(
                DocumentVersion,
                DocumentVersion.document_id == Document.id,
            )
            .where(DocumentVersion.id.is_(None))
            .distinct()
        )
        result = await db.execute(stmt)
        documents = result.scalars().all()

        total = len(documents)
        logger.info(f"Found {total} documents without versions")

        migrated = 0
        skipped = 0
        errors = 0

        for doc in documents:
            try:
                # Read existing file from storage
                file_content = None
                original_file_path = None

                # Try the stored file_path
                if doc.file_path:
                    try:
                        file_content = await storage.get(doc.file_path)
                        original_file_path = doc.file_path
                    except (FileNotFoundError, Exception):
                        pass

                if file_content is None:
                    logger.warning(
                        f"SKIP doc {doc.id}: no file found at '{doc.file_path}', "
                        "creating stub version"
                    )
                    # Create a stub version record without a file
                    version = DocumentVersion(
                        document_id=doc.id,
                        version_number=1,
                        file_path=doc.file_path or "",
                        file_type="docx",
                        file_size=doc.file_size or 0,
                        mime_type="application/octet-stream",
                        file_hash=None,
                        uploaded_by=doc.created_by,
                        created_at=doc.created_at,
                    )
                    db.add(version)
                    await db.flush()
                    skipped += 1
                    continue

                # Compute hash
                file_hash = hashlib.sha256(file_content).hexdigest()
                file_size = len(file_content)

                # Determine filename
                filename = os.path.basename(doc.file_path or "document.docx")

                # Save to versioned path using storage service
                version_path = await storage.save_version_file(
                    document=doc,
                    version_number=1,
                    file_content=file_content,
                    filename=filename,
                )

                # Determine file_type and mime_type
                ext = os.path.splitext(filename)[1].lower().replace(".", "")
                file_type = "docx" if ext == "docx" else "pdf" if ext == "pdf" else ext
                mime_types = {
                    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "pdf": "application/pdf",
                }
                mime_type = mime_types.get(file_type, "application/octet-stream")

                # Create version record
                version = DocumentVersion(
                    document_id=doc.id,
                    version_number=1,
                    file_path=version_path,
                    file_type=file_type,
                    file_size=file_size,
                    mime_type=mime_type,
                    file_hash=file_hash,
                    uploaded_by=doc.created_by,
                    created_at=doc.created_at,
                )
                db.add(version)
                await db.flush()

                # Update document metadata
                doc.file_path = version_path
                doc.file_hash = file_hash
                doc.file_size = file_size

                migrated += 1
                logger.info(
                    f"MIGRATED doc {doc.id}: v1 created ({filename}, "
                    f"{file_size} bytes, hash={file_hash[:16]}...)"
                )

            except Exception as e:
                logger.error(f"ERROR doc {doc.id}: {e}", exc_info=True)
                errors += 1
                await db.rollback()
                # Re-create session after rollback
                return

            # Batch progress
            if (migrated + skipped + errors) % BATCH_SIZE == 0:
                logger.info(
                    f"Progress: {migrated} migrated, {skipped} skipped, "
                    f"{errors} errors / {total} total"
                )

        await db.commit()
        logger.info(
            f"Migration complete: {total} docs processed, "
            f"{migrated} migrated, {skipped} skipped, {errors} errors"
        )

    # ── Step 2: Migrate analyses without document_version_id ──────────
    await migrate_analysis_version_ids()


async def migrate_analysis_version_ids():
    """Set document_version_id for analyses that don't have it."""
    async with async_session() as db:
        stmt = select(DocumentAnalysis).where(
            DocumentAnalysis.document_version_id.is_(None)
        )
        result = await db.execute(stmt)
        analyses = result.scalars().all()

        updated = 0
        for analysis in analyses:
            try:
                # Find the latest version at the time of analysis
                ver_stmt = (
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == analysis.document_id)
                    .where(DocumentVersion.created_at <= analysis.created_at)
                    .order_by(DocumentVersion.version_number.desc())
                    .limit(1)
                )
                ver_result = await db.execute(ver_stmt)
                version = ver_result.scalar_one_or_none()

                if version:
                    analysis.document_version_id = version.id
                    updated += 1
            except Exception as e:
                logger.error(
                    f"Failed to migrate analysis {analysis.id}: {e}"
                )

        await db.commit()
        logger.info(f"Updated {updated} analyses with version IDs")


if __name__ == "__main__":
    asyncio.run(migrate_documents())
