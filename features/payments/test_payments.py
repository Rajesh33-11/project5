import pytest

from pages.payments_page import PaymentsPage


@pytest.mark.smoke
def test_payments_page_loads(page, base_url):
    p = PaymentsPage(page, base_url)
    p.open()
    assert p.is_loaded()
