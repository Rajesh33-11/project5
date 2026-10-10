from pages.base_page import BasePage


class PaymentsPage(BasePage):
    PATH = "/payments"

    def is_loaded(self) -> bool:
        return self.page.url.rstrip("/").endswith(self.PATH)
