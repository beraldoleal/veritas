"""Unit tests for `veritas collateral render` (no cluster or network needed)."""

import base64
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from veritas import collaterals
from veritas.collaterals import snp

DATA = Path(__file__).parent / "data"
# Real Milan VCEK from Trustee test data (deps/verifier/test_data/snp).
MILAN_VCEK = (DATA / "milan-vcek.der").read_bytes()
# https://kdsintf.amd.com/vcek/v1/Milan/cert_chain
MILAN_CHAIN = (DATA / "milan-cert-chain.pem").read_bytes()
HWID = "ab" * 64
NODE = {"name": "w0", "tee": "snp", "product": "Milan", "hwid": HWID,
        "tcb": {"blSPL": 3, "teeSPL": 0, "snpSPL": 8, "ucodeSPL": 115}}
VCEK_FILE = "bl03_tee00_snp08_ucode115_vcek.der"

needs_snpguest = pytest.mark.skipif(not shutil.which("snpguest"), reason="snpguest not installed")


@needs_snpguest
class TestVerifyCerts:
    def test_wrong_chain(self):
        chain = snp.split_cert_chain(MILAN_CHAIN)
        with pytest.raises(RuntimeError, match="verification failed"):
            snp.verify_certs(chain["ark.pem"], chain["ark.pem"], MILAN_VCEK)


@pytest.fixture
def offline(monkeypatch):
    urls = []

    def fetch(url):
        urls.append(url)
        return MILAN_CHAIN if url.endswith("/cert_chain") else MILAN_VCEK

    monkeypatch.setattr(snp, "fetch", fetch)
    if not shutil.which("snpguest"):
        monkeypatch.setattr(snp, "verify_certs", lambda ark, ask, vcek: None)
    return urls


def write_request(tmp_path, nodes):
    p = tmp_path / "request.json"
    p.write_text(json.dumps({"version": 1, "nodes": nodes}))
    return str(p)


class TestRender:
    def test_writes_manifests_and_bundle(self, tmp_path, offline):
        req = write_request(tmp_path, [NODE, {**NODE, "name": "w1"}])
        kbsconfig = tmp_path / "kbsconfig.json"
        kbsconfig.write_text(json.dumps({
            "metadata": {"name": "trustee-kbsconfig"},
            "spec": {"kbsLocalCertCacheSpec": {"secrets": [
                {"secretName": "tdx-collateral", "mountPath": "/tdx"}]}}}))
        out = tmp_path / "manifests"
        bundle = tmp_path / "bundle.tar"

        collaterals.main(["render", req, "--kbsconfig", str(kbsconfig),
                          "-o", str(out), "-b", str(bundle)])

        assert len(offline) == 2  # cert chain + one VCEK, same chip on two nodes
        secrets = (out / "secrets.yaml").read_text()
        assert f"name: vcek-{HWID[:16]}" in secrets
        assert f"{VCEK_FILE}: {base64.b64encode(MILAN_VCEK).decode()}" in secrets
        patch = (out / "kbsconfig.patch").read_text()
        assert "secretName: tdx-collateral" in patch
        assert f"kds-store/vcek/{HWID}" in patch
        with tarfile.open(bundle) as tar:
            assert sorted(tar.getnames()) == sorted(
                f"vcek/{HWID}/{n}" for n in ("ark.pem", "ask.pem", VCEK_FILE))
