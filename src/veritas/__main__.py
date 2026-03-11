"""Extract CoCo reference values for Trustee RVPS."""

import argparse
import logging
import sys
from pathlib import Path

from veritas.models import format_trustee
from veritas.platforms import EXTRACTORS

log = logging.getLogger(__name__)

RVPS_FILENAME = "rvps-reference-values.yaml"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=EXTRACTORS.keys())
    parser.add_argument("--tee", default="tdx", choices=["tdx", "snp"])
    parser.add_argument("--authfile", help="Registry auth file for pulling images")
    parser.add_argument("--initdata", help="Path to initdata.toml for hash computation")
    parser.add_argument("-o", "--output", default=".",
                        help="Output directory (default: current directory)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        extractor_cls = EXTRACTORS[args.platform]
        extractor = extractor_cls(tee=args.tee, authfile=args.authfile)
        values = extractor.extract()
        if args.initdata:
            values.append(extractor.compute_initdata(args.initdata))
    except RuntimeError as e:
        log.error("%s", e)
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    rvps_path = output_dir / RVPS_FILENAME
    rvps_path.write_text(format_trustee(values, extractor.platform, args.tee))
    log.info("Written %s", rvps_path)


if __name__ == "__main__":
    main()
