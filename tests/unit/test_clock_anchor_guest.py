"""Run the portable guest parser as C, including embedded NUL/length failures."""

import hashlib
import json
import subprocess
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = r"""
#include "clock_anchor.h"
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    const char *texts[] = {"c2b-markers=0", "c2b-markers=1", "", "c2b-markers=2",
        " c2b-markers=1", "c2b-markers=1 ", "c2b-markers=1 extra",
        "c2b-mark\0rs=1", "c2b-markers=1", "c2b-markers=1", "c2b-markers=1X"};
    const unsigned lengths[] = {13,13,0,13,14,14,19,13,12,14,13};
    if (argc != 2) return 2;
    unsigned i = (unsigned)strtoul(argv[1], NULL, 10), mode = 77;
    int result;
    if (i < 11) result = poc_clock_parse_mode(texts[i], lengths[i], &mode);
    else if (i == 11) result = poc_clock_parse_mode(NULL, 13, &mode);
    else result = poc_clock_parse_mode("c2b-markers=1", 13, NULL);
    printf("%d %u\n", result, mode);
    return 0;
}
"""


class ClockGuestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = ROOT / "runs/local/c2b-native-tests" / uuid.uuid4().hex
        cls.output.mkdir(parents=True)
        cls.source = cls.output / "guest-parser.c"
        cls.source.write_text(HARNESS)
        cls.binary = cls.output / "guest-parser"
        cmd = [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I" + str(ROOT / "firmware/port"),
            str(cls.source),
            "-o",
            str(cls.binary),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        cls.save("compile", cmd, result)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors="replace"))

    @classmethod
    def save(cls, name, cmd, result):
        (cls.output / f"{name}.stdout").write_bytes(result.stdout)
        (cls.output / f"{name}.stderr").write_bytes(result.stderr)
        (cls.output / f"{name}.json").write_text(
            json.dumps(
                dict(
                    command=cmd,
                    exit=result.returncode,
                    harness_sha256=hashlib.sha256(cls.source.read_bytes()).hexdigest(),
                ),
                indent=2,
            )
            + "\n"
        )

    def test_exact_modes_and_no_default_on_invalid_input(self):
        for i in range(13):
            cmd = [str(self.binary), str(i)]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            self.save(f"case-{i}", cmd, result)
            with self.subTest(case=i):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout, b"0 0\n" if i == 0 else b"0 1\n" if i == 1 else b"-1 77\n"
                )
