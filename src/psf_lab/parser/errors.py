"""Structured errors retain the exact byte position of a rejected input."""


class ParseError(ValueError):
    def __init__(self, code: str, offset: int, message: str):
        super().__init__(f"{code} at byte {offset}: {message}")
        self.code = code
        self.offset = offset
        self.message = message
