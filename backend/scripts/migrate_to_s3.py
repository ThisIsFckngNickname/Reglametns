"""
Скрипт для миграции файлов из локального хранилища в S3-совместимое.

Запуск:
    python scripts/migrate_to_s3.py

Требует настроенных переменных окружения для S3 (или .env файла):
    STORAGE_TYPE=s3
    S3_ENDPOINT_URL=http://localhost:9000
    S3_ACCESS_KEY=minioadmin
    S3_SECRET_KEY=minioadmin
    S3_BUCKET=srp-documents

Локальные файлы не удаляются после миграции (dry-run безопасен).
"""

import asyncio
import logging
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def migrate() -> None:
    """Migrate all files from local storage to S3."""
    from app.config import settings
    from app.storage.local import LocalStorage
    from app.storage.s3 import S3Storage

    # === 1. Определяем источники ===
    upload_dir = settings.upload_dir
    local_storage = LocalStorage(base_dir=upload_dir)

    # === 2. Определяем приёмник ===
    s3_storage = S3Storage(
        bucket=settings.s3_bucket,
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
    )

    # === 3. Проверяем доступность S3 ===
    try:
        # Пробуем записать тестовый объект
        await s3_storage.save(".migration-test", b"test")
        await s3_storage.delete(".migration-test")
        logger.info("S3 доступен. Начинаем миграцию...")
    except Exception as e:
        logger.error(f"S3 недоступен: {e}")
        logger.error("Миграция прервана. Проверьте настройки S3.")
        return

    # === 4. Сканируем локальные файлы ===
    base_path = Path(upload_dir).resolve()
    if not base_path.exists():
        logger.warning(f"Директория {upload_dir} не существует. Нечего мигрировать.")
        return

    file_count = 0
    error_count = 0

    for file_path in sorted(base_path.rglob("*")):
        if not file_path.is_file():
            continue

        relative = file_path.relative_to(base_path).as_posix()
        logger.info(f"[{file_count + 1}] Мигрирую: {relative}")

        try:
            content = local_storage.read(relative)  # sync read is fine here
            # content is bytes — await not needed for sync method
            if asyncio.iscoroutine(content):
                content = await content

            await s3_storage.save(relative, content)
            file_count += 1
            logger.info(f"  ✓ {relative} ({len(content)} bytes)")

        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ {relative}: {e}")

    # === 5. Итог ===
    logger.info("=" * 50)
    logger.info(f"Миграция завершена.")
    logger.info(f"  Успешно: {file_count}")
    logger.info(f"  Ошибок:  {error_count}")
    logger.info(f"  Источник: {upload_dir}")
    logger.info(f"  Цель:     s3://{settings.s3_bucket}/")
    logger.info("=" * 50)
    logger.info(
        "ВАЖНО: Локальные файлы НЕ были удалены. "
        "После проверки миграции удалите их вручную или через скрипт очистки."
    )


if __name__ == "__main__":
    asyncio.run(migrate())
