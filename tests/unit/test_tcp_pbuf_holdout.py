"""Guest receipt must prove the callback saw a real fragmented request."""

import copy
import unittest

from psf_lab import tcp_session


class PbufReceiptTests(unittest.TestCase):
    def validate(self, metrics, workload):
        self.assertTrue(
            hasattr(tcp_session, "validate_request_pbufs"),
            "Guest chain receipt validator not implemented",
        )
        return tcp_session.validate_request_pbufs(metrics, workload)

    def test_two_real_chains(self):
        metrics = {"request_pbufs": [dict(lengths=[13, 0, 51], totals=[64, 51, 51])] * 2}
        self.assertEqual(
            self.validate(metrics, "fragmented"), {"requests": 2, "nodes": 6, "empty_nodes": 2}
        )

    def test_missing_single_segment_or_bad_total_rejected(self):
        good = dict(lengths=[13, 0, 51], totals=[64, 51, 51])
        for shapes in (
            None,
            [],
            [good],
            [dict(lengths=[64], totals=[64])] * 2,
            [dict(lengths=[13, 0, 51], totals=[64, 0, 51])] * 2,
            [dict(lengths=[13, 1, 50], totals=[64, 51, 50])] * 2,
            [dict(lengths=[13, False, 51], totals=[64, 51, 51])] * 2,
            [dict(lengths=[13, 0, 51], totals=[64.0, 51, 51])] * 2,
        ):
            metrics = {} if shapes is None else {"request_pbufs": copy.deepcopy(shapes)}
            with self.assertRaisesRegex(ValueError, "pbuf"):
                self.validate(metrics, "fragmented")

    def test_unknown_workload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "workload"):
            self.validate({}, "wrong")

    def test_linear_does_not_claim_chain_evidence(self):
        self.assertEqual(
            self.validate({}, "linear"), {"requests": 2, "nodes": None, "empty_nodes": None}
        )
        with self.assertRaisesRegex(ValueError, "pbuf"):
            self.validate({"request_pbufs": []}, "linear")
