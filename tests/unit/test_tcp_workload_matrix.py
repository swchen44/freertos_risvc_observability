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

    def test_evidence_hash_tamper_is_rejected(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from psf_lab.runner import digest
        from psf_lab.tcp_workload_matrix import checked

        with TemporaryDirectory() as temp:
            path = Path(temp) / "packet.bin"
            path.write_bytes(b"original")
            expected = digest(path)
            checked(path, expected)
            path.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "Evidence hash mismatch"):
                checked(path, expected)

    def test_missing_group_is_rejected(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from psf_lab.tcp_workload_matrix import analyze_matrix

        with TemporaryDirectory() as temp:
            root = Path(temp)
            runs = root / "runs"
            runs.mkdir()
            (runs / "A01-baseline").mkdir()
            with self.assertRaisesRegex(ValueError, "sixteen"):
                analyze_matrix(root, runs, root / "results")
