import requests


class Nobitex:
    """Get the Currency price(rial) from nobitex"""

    def __init__(self, currency="usdt"):
        self.currency = currency
        self.base_api = "https://sec-gray.ir/nobitex/nobitex.json"

    def get_symbol_price(self, retry=5):
        if retry <= 0:
            return 500000

        currency_price = None
        data = requests.get(self.base_api).json()
        if data.get("status") == "ok":
            currency_price = (
                data.get("stats", {}).get(f"{self.currency}-rls", {}).get("bestBuy")
            )

        if currency_price:
            return int(currency_price)
        else:
            self.get_symbol_price(retry=retry - 1)


if __name__ == "__main__":
    price = Nobitex().get_symbol_price()
    print(price)
