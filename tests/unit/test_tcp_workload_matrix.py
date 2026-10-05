import unittest

from psf_lab.tcp_workload_matrix import validate_attempts


class MatrixTests(unittest.TestCase):
    def test_complete_pairs_and_missing_repeat(self):
        rows = [dict(enabled=bool(e), repeat=n, accepted=True) for e in (0, 1) for n in (1, 2, 3)]
        validate_attempts(rows)
        for broken in (rows[:-1], rows + [rows[0]], [{**r, "accepted": False} for r in rows]):
            with self.assertRaises(ValueError):
                validate_attempts(broken)

    def test_boolean_repeat_and_duplicate_rejected(self):
        rows = [dict(enabled=bool(e), repeat=n, accepted=True) for e in (0, 1) for n in (1, 2, 3)]
        rows[0]["repeat"] = True
        with self.assertRaises(ValueError):
            validate_attempts(rows)
