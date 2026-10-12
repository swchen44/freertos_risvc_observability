"""Export one verified workload as offline HTML."""

import argparse
import json
from pathlib import Path

from psf_lab.hotspot_export import export_hotspot_html

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workload", required=True)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    receipt = export_hotspot_html(Path.cwd(), a.workload, a.output)
    a.output.with_suffix(".receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
