class TransactionPaidBefore(Exception):
    def __init__(self, message="Transaction has already been paid"):
        self.message = message
        super().__init__(self.message)
