"""Export one full event-window workload; never overwrite existing HTML."""

import argparse
import json
from pathlib import Path

from psf_lab.event_window_export import export_event_window_html

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workload", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    receipt = export_event_window_html(Path.cwd(), a.workload, a.output)
    a.output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
