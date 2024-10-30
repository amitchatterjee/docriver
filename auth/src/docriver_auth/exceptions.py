class AuthorizationException(Exception):
    def __init__(self, message="Authorization exception"):
        self.message = message
        super().__init__(self.message)
