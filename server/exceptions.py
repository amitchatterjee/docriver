class ValidationException(Exception):
    def __init__(self, message="Validation exception"):
        self.message = message
        super().__init__(self.message)