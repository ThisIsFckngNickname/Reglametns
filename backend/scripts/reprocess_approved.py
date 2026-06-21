import asyncio, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sqlalchemy import select
from app.database import async_session
from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.services.pattern_analysis_service import pattern_analysis_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def reprocess():
    async with async_session() as db:
        stmt = select(Document).where(Document.status == DocumentStatus.APPROVED, Document.was_analyzed.is_(False))
        docs = (await db.execute(stmt)).scalars().all()
        logger.info(f"Found {len(docs)} document(s) to reprocess")
        for doc in docs:
            logger.info(f"Processing #{doc.id} ({doc.title})...")
            try:
                r = await pattern_analysis_service.analyze_document(document_id=doc.id, db=db)
                if "error" in r:
                    logger.warning(f"  skip: {r['error']}")
                else:
                    logger.info(f"  done: struct={r.get('structure_extracted')} style={r.get('style_extracted')}")
            except Exception as e:
                logger.error(f"  fail: {e}", exc_info=True)
        await db.commit()

def main():
    asyncio.run(reprocess())

if __name__ == "__main__":
    main()
