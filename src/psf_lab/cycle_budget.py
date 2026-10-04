"""Exact cumulative conversion for future serial service costs, no QEMU injection."""


class CycleBudget:
    def __init__(self, frequency_hz):
        if type(frequency_hz) is not int or frequency_hz <= 0:
            raise ValueError("Frequency must be a positive integer Hz")
        self.frequency_hz = frequency_hz
        self.elapsed_ns = 0
        self._remainder = 0

    def add(self, cycles):
        if type(cycles) is not int or cycles < 0:
            raise ValueError("Cost must be nonnegative integer cycles")
        increment, remainder = divmod(self._remainder + cycles * 1_000_000_000, self.frequency_hz)
        if self.elapsed_ns + increment > 2**63 - 1:
            raise OverflowError("Accumulated cost exceeds signed QEMU nanoseconds")
        self.elapsed_ns += increment
        self._remainder = remainder
        return increment
