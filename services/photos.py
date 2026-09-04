from dataclasses import dataclass
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile

from schemas import PhotoReference


class PhotoLimitError(ValueError): pass


@dataclass(frozen=True, slots=True)
class PhotoLimits:
    max_count: int = 20
    max_size_bytes: int = 10_485_760
    max_total_bytes: int = 52_428_800


class PhotoCollection:
    def __init__(self, photos: list[PhotoReference] | None = None) -> None:
        self.photos = list(photos or [])

    def add(self, *, file_id: str, unique_id: str | None, mime_type: str,
            size_bytes: int | None, media_group_id: str | None, limits: PhotoLimits) -> bool:
        if any((unique_id and item.telegram_file_unique_id == unique_id)
               or (not unique_id and item.telegram_file_id == file_id) for item in self.photos): return False
        if len(self.photos) >= limits.max_count: raise PhotoLimitError("Достигнут лимит фотографий")
        if size_bytes is not None and size_bytes > limits.max_size_bytes: raise PhotoLimitError("Файл слишком большой")
        total = sum(item.size_bytes or 0 for item in self.photos) + (size_bytes or 0)
        if total > limits.max_total_bytes: raise PhotoLimitError("Превышен общий размер фотографий")
        self.photos.append(PhotoReference(telegram_file_id=file_id, telegram_file_unique_id=unique_id,
                           order_number=len(self.photos) + 1, mime_type=mime_type,
                           size_bytes=size_bytes, media_group_id=media_group_id))
        return True

    def remove_last(self) -> None:
        if self.photos: self.photos.pop()

    def clear(self) -> None: self.photos.clear()

    def dump(self) -> list[dict]: return [item.model_dump(mode="json", exclude={"local_temp_path"}) for item in self.photos]


@asynccontextmanager
async def temporary_analysis_directory(analysis_id: int):
    path = Path(tempfile.mkdtemp(prefix=f"auto-analysis-{analysis_id}-"))
    try:
        yield path
    finally:
        import asyncio
        await asyncio.to_thread(shutil.rmtree, path, True)
