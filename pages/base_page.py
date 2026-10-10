class BasePage:
    PATH = "/"

    def __init__(self, page, base_url: str):
        self.page = page
        self.base_url = base_url

    def open(self):
        self.page.goto(f"{self.base_url}{self.PATH}")
        return self
