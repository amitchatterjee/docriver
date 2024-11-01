class ValidationException(Exception):
    def __init__(self, message="Validation exception"):
        self.message = message
        super().__init__(self.message)

class DocumentException(Exception):
    def __init__(self, message="Document exception"):
        self.message = message
        super().__init__(self.message)