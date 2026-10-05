"""Verify independent -Os experiments and export miss attribution and comparisons.

Run from the POC root. Inputs are relative run directories, ordered standard,
small baseline, layout, checksum, pbuf. Outputs retain map/assembly evidence.
"""

import argparse
import csv
import gzip
import json
import subprocess
from pathlib import Path

from psf_lab.live_cache_irq import compare_irq, validate_irq_trace
from psf_lab.parser.semantic import parse_trace
from psf_lab.runner import digest, write_json
from psf_lab.tcp_hotspots import profile_misses
from psf_lab.tcp_packets import decode_packet
from psf_lab.tcp_session import validate_session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs=5, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    toolchain = root / ".tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin"
    packet_reference = None
    env_reference = None
    summaries = []
    for label, directory in zip(
        ("standard", "baseline", "layout", "checksum", "pbuf"), args.runs, strict=True
    ):
        manifest = json.loads((directory / "manifest.json").read_text())
        result = json.loads((directory / "results.json").read_text())
        assert digest(directory / "results.json") == manifest["results_sha256"]
        assert result["passed"] and result["repeatable"], directory
        for path, sha in manifest["sources"].items():
            assert digest(root / path) == sha, path
        assert manifest["checksum_opt"] == "Os"
        assert manifest["tcp_variant"] == ("baseline" if label == "standard" else label)
        assert manifest["cache_profile"].endswith(
            "sysram-10.json" if label == "standard" else "sysram-10-small.json"
        )
        env = {
            k: manifest[k] for k in ("qemu_sha256", "gcc_sha256", "frequency_hz", "icount_shift")
        }
        if env_reference is None:
            env_reference = env
        assert env == env_reference
        compile_lines = [
            line
            for line in (directory / "build.log").read_text().splitlines()
            if " -c " in line and "riscv-none-elf-gcc" in line
        ]
        assert compile_lines
        for line in compile_lines:
            opts = [word for word in line.split() if word.startswith("-O")]
            assert opts and all(opt == "-Os" for opt in opts), line
        for record in manifest["runs"]:
            path = directory / record["name"]
            assert digest(path / "manifest.json") == record["sha256"]
            rm = json.loads((path / "manifest.json").read_text())
            for file, sha in rm["files"].items():
                assert digest(path / file) == sha, path / file
            entry = rm["result"]
            assert entry["accepted"]
            assert (
                validate_irq_trace(
                    parse_trace((path / "trace.psf").read_bytes()),
                    entry["measurement"],
                    scenario="tcp",
                )
                == entry["switches"]
            )
            metrics = json.loads((path / "session.json").read_text())
            packets = [
                dict(decode_packet((path / x["file"]).read_bytes()), direction=x["direction"])
                for x in metrics["packets"]
            ]
            assert validate_session(packets, metrics) == entry["tcp"]
            packet_hashes = [digest(path / x["file"]) for x in metrics["packets"]]
            if packet_reference is None:
                packet_reference = packet_hashes
            assert packet_hashes == packet_reference, path
        for comparison in result["comparisons"]:
            pair = [r for r in result["runs"] if r["repeat"] == comparison["repeat"]]
            control = next(r for r in pair if not r["enabled"])
            active = next(r for r in pair if r["enabled"])
            checked = compare_irq(
                control["measurement"],
                active["measurement"],
                control["audit"],
                active["audit"],
                scenario="tcp",
            )
            assert checked == {
                k: v for k, v in comparison.items() if k not in ("accepted", "repeat")
            }
        entry = next(r for r in result["runs"] if r["enabled"])
        path = directory / entry["run"]
        symbols = []
        for line in (path / "symbols.txt").read_text().splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[2] in ("T", "t"):
                symbols.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
        named = {s[2]: s for s in symbols}
        profile = json.loads((root / manifest["cache_profile"]).read_text())
        with gzip.open(path / "accesses.csv.gz", "rt") as stream:
            stats = profile_misses(
                csv.DictReader(stream),
                profile,
                symbols,
                stack_markers=(named["z0_stack_begin"][0], named["z0_stack_end"][0]),
            )
        assert stats["windows"] == 27
        assert stats["totals"]["cycles"] == entry["audit"]["cycles"]
        assert stats["events"] == entry["audit"]["events"]
        for level in ("l1i", "l1d", "l2"):
            assert stats["model"][level]["misses"] == sum(
                stats["totals"].get(level + "_" + kind, 0)
                for kind in ("compulsory", "conflict", "capacity")
            )
        top_pcs = sorted(
            {
                row["pc"]
                for level in ("l1i", "l1d", "l2")
                for row in sorted(
                    stats["pcs"], key=lambda r: r.get(level + "_misses", 0), reverse=True
                )[:12]
            }
        )
        locations = subprocess.check_output(
            [
                str(toolchain / "riscv-none-elf-addr2line"),
                "-f",
                "-i",
                "-a",
                "-e",
                str(path / "firmware.elf"),
                *map(hex, top_pcs),
            ],
            text=True,
        )
        (output / f"{label}-locations.txt").write_text(locations)
        (output / f"{label}-assembly.txt").write_text(
            subprocess.check_output(
                [str(toolchain / "riscv-none-elf-objdump"), "-d", str(path / "firmware.elf")],
                text=True,
            )
        )
        size_text = subprocess.check_output(
            [str(toolchain / "riscv-none-elf-size"), str(path / "firmware.elf")], text=True
        )
        (output / f"{label}-size.txt").write_text(size_text)
        text, data, bss = map(int, size_text.splitlines()[1].split()[:3])
        map_path = output / f"{label}-firmware.map"
        if not map_path.exists():
            map_path.write_bytes((directory / "build/firmware.map").read_bytes())
        write_json(output / f"{label}-profile.json", stats)
        m = entry["measurement"]
        summary = dict(
            label=label,
            run=str(directory),
            repeats=len(result["runs"]) // 2,
            guest_ns=(m["after"] - m["before"]) * 100,
            text=text,
            data=data,
            bss=bss,
            ticks=m["ticks"],
            **stats["totals"],
            stack_cycles=stats["scopes"]["stack_window_including_preemption"]["cycles"],
            harness_cycles=stats["scopes"]["harness_window"]["cycles"],
            cost_cycles=stats["model"]["cost_cycles"],
            function_sizes={
                k: dict(address=hex(v[0]), size=v[1])
                for k, v in named.items()
                if k
                in (
                    "lwip_standard_chksum",
                    "poc_endpoint_chksum",
                    "on_recv",
                    "tcp_input",
                    "tcp_output",
                    "tcp_receive",
                )
            },
        )
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
    write_json(
        output / "comparison.json",
        dict(
            schema="tcp-os-small-cache-v1",
            passed=True,
            environment=env_reference,
            packet_hashes=packet_reference,
            results=summaries,
            analysis_sources={
                str(p): digest(p)
                for p in (Path(__file__).relative_to(root), Path("src/psf_lab/tcp_hotspots.py"))
            },
        ),
    )
    fields = [
        "label",
        "guest_ns",
        "cycles",
        "instructions",
        "stack_cycles",
        "harness_cycles",
        "text",
        "data",
        "bss",
        "l1i_misses",
        "l1d_misses",
        "l2_misses",
    ]
    with (output / "comparison.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)
    write_json(
        output / "SHA256.json",
        {p.name: digest(p) for p in output.iterdir() if p.is_file() and p.name != "SHA256.json"},
    )


if __name__ == "__main__":
    main()
