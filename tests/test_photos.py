import pytest
from services.photos import (PhotoCollection, PhotoLimitError, PhotoLimits,
                             temporary_analysis_directory)

def test_order_duplicates_remove_clear_and_limits():
    collection = PhotoCollection(); limits = PhotoLimits(2, 10, 15)
    assert collection.add(file_id="1", unique_id="a", mime_type="image/jpeg", size_bytes=5, media_group_id="g", limits=limits)
    assert not collection.add(file_id="1x", unique_id="a", mime_type="image/jpeg", size_bytes=5, media_group_id="g", limits=limits)
    collection.add(file_id="2", unique_id="b", mime_type="image/png", size_bytes=5, media_group_id="g", limits=limits)
    assert [p.order_number for p in collection.photos] == [1, 2]
    with pytest.raises(PhotoLimitError): collection.add(file_id="3", unique_id="c", mime_type="image/jpeg", size_bytes=1, media_group_id=None, limits=limits)
    collection.remove_last(); assert len(collection.photos) == 1
    collection.clear(); assert collection.photos == []

@pytest.mark.asyncio
@pytest.mark.parametrize("fail",[False,True])
async def test_temp_directory_removed_on_success_and_exception(fail):
    path=None
    with pytest.raises(RuntimeError) if fail else __import__("contextlib").nullcontext():
        async with temporary_analysis_directory(42) as current:
            path=current; (current/"image.jpg").write_bytes(b"x")
            if fail: raise RuntimeError("boom")
    assert path is not None and not path.exists()
