"""AMD SEV-SNP collateral (VCEK certificates)."""

import re
from urllib.parse import parse_qs, urlparse

KDS_HOST = "kdsintf.amd.com"
PRODUCTS = {"Milan", "Genoa", "Turin"}
TCB_FIELDS = ("blSPL", "teeSPL", "snpSPL", "ucodeSPL", "fmcSPL")


def parse_vcek_url(url: str) -> dict:
    """Parse and validate `snphost show vcek-url` output.

    The URL comes from the node, so it is untrusted input.
    """
    u = urlparse(url.strip())
    if u.scheme != "https" or u.hostname != KDS_HOST:
        raise ValueError(f"Unexpected VCEK URL host: {url}")

    m = re.fullmatch(r"/vcek/v1/(\w+)/([0-9a-fA-F]+)", u.path)
    if not m or m.group(1) not in PRODUCTS:
        raise ValueError(f"Unexpected VCEK URL path: {u.path}")
    product, hwid = m.group(1), m.group(2).lower()  # Trustee looks up lowercase
    if len(hwid) != (16 if product == "Turin" else 128):
        raise ValueError(f"Unexpected hwid length for {product}: {len(hwid)}")

    tcb = {}
    for key, vals in parse_qs(u.query, strict_parsing=True).items():
        if key not in TCB_FIELDS or len(vals) != 1 or not vals[0].isdigit():
            raise ValueError(f"Unexpected VCEK URL parameter: {key}")
        spl = int(vals[0])
        if spl > 255:
            raise ValueError(f"{key} out of range: {spl}")
        tcb[key] = spl

    return {"product": product, "hwid": hwid, "tcb": tcb}
