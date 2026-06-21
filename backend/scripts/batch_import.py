"""
Batch import script to import documents from mytemps/ into the system.

Usage:
    python -m scripts.batch_import --holding-id=1 --source=../../mytemps

This script:
1. Scans the source directory for .docx and .pdf files
2. Uploads each file via the API
3. Sets status to "approved" to trigger pattern analysis
4. Reports results
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def upload_document(client: httpx.AsyncClient, api_url: str, token: str, file_path: str, holding_id: int) -> dict:
    """Upload a single document."""
    filename = os.path.basename(file_path)
    category = os.path.basename(os.path.dirname(file_path))

    with open(file_path, "rb") as f:
        files = {"file": (filename, f, "application/octet-stream")}
        data = {
            "title": f"{category} - {os.path.splitext(filename)[0]}",
            "description": f"Imported from {category}",
        }
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            f"{api_url}/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers,
        )

    if resp.status_code == 201:
        doc = resp.json()
        logger.info(f"  Uploaded: {filename} -> document #{doc['id']}")
        return doc
    else:
        logger.error(f"  Failed: {filename} - {resp.status_code}: {resp.text}")
        return {"error": resp.text, "filename": filename}


async def approve_document(client: httpx.AsyncClient, api_url: str, token: str, document_id: int) -> dict:
    """Set document status to approved to trigger pattern analysis."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.put(
        f"{api_url}/api/v1/documents/{document_id}",
        json={"status": "approved"},
        headers=headers,
    )

    if resp.status_code == 200:
        doc = resp.json()
        logger.info(f"  Approved: document #{document_id}")
        return doc
    else:
        logger.error(f"  Failed to approve #{document_id}: {resp.status_code}: {resp.text}")
        return {"error": resp.text, "document_id": document_id}


async def main():
    parser = argparse.ArgumentParser(description="Batch import documents from directory")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--token", required=True, help="Auth token for API")
    parser.add_argument("--holding-id", type=int, required=True, help="Holding ID")
    parser.add_argument("--source", default="../../mytemps", help="Source directory with documents")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve imported documents")
    args = parser.parse_args()

    source_dir = Path(args.source)
    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return

    # Find all .docx and .pdf files
    files = []
    for ext in ("*.docx", "*.pdf"):
        files.extend(source_dir.rglob(ext))

    # Filter out temp files (starting with ~$)
    files = [f for f in files if not f.name.startswith("~$")]

    logger.info(f"Found {len(files)} documents in {source_dir}")

    async with httpx.AsyncClient(timeout=120) as client:
        # Step 1: Upload
        uploaded = []
        for file_path in sorted(files):
            try:
                doc = await upload_document(client, args.api_url, args.token, str(file_path), args.holding_id)
                if "id" in doc:
                    uploaded.append(doc)
            except Exception as e:
                logger.error(f"  Error uploading {file_path}: {e}")

        logger.info(f"\nUploaded {len(uploaded)}/{len(files)} documents")

        # Step 2: Auto-approve if requested
        if args.auto_approve and uploaded:
            logger.info("\n--- Approving documents ---")
            for doc in uploaded:
                try:
                    await approve_document(client, args.api_url, args.token, doc["id"])
                except Exception as e:
                    logger.error(f"  Error approving #{doc['id']}: {e}")

        # Summary
        logger.info("\n--- Summary ---")
        logger.info(f"Total files found: {len(files)}")
        logger.info(f"Successfully uploaded: {len(uploaded)}")
        if args.auto_approve:
            logger.info(f"Auto-approved: {len(uploaded)}")


if __name__ == "__main__":
    asyncio.run(main())
