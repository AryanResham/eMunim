"""Isolated services for Playwright; never opens the normal records database."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "research"), str(ROOT / "scripts")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("service", choices=["backend", "annotation"])
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    from verify_all_types import fixtures
    if args.service == "backend":
        from config import settings
        settings.DATA_DIR = str(args.workspace / "data")
        settings.DATABASE_URL = "sqlite:///" + (args.workspace / "browser.db").as_posix()
        settings.RESEARCH_REPORT_DIR = str(args.workspace / "research")
        settings.ALLOWED_ORIGINS = ["http://127.0.0.1:5176"]
        settings.HOSTED_VLM_MAX_ATTEMPTS = 2
        import torch
        torch.set_num_threads(4)
        import uvicorn
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
    else:
        fixtures(args.workspace / "fixtures")
        from annotate import prepare, serve
        folder = args.workspace / "annotations"
        prepare(args.workspace / "fixtures/images/gst_invoice.png", folder, "GST_INVOICE")
        prepare(args.workspace / "fixtures/images/purchase_bill.png", folder, "PURCHASE_BILL")
        serve(folder, 8766)


if __name__ == "__main__":
    main()
