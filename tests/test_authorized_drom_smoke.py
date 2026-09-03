import os
import pytest

@pytest.mark.authorized_drom_smoke
@pytest.mark.skipif(os.getenv("RUN_AUTHORIZED_DROM_SMOKE")!="true",
                    reason="requires explicit permission and RUN_AUTHORIZED_DROM_SMOKE=true")
def test_authorized_drom_smoke_requires_external_permission():
    pytest.skip("Run only with owner-provided permission and an explicit local smoke implementation")
