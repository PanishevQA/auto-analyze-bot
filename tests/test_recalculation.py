from unittest.mock import AsyncMock
from handlers.history import recalc_price

def test_recalculation_handler_has_no_external_clients():
    names=set(recalc_price.__code__.co_varnames[:recalc_price.__code__.co_argcount])
    assert "apipoint" not in names and "vision" not in names
