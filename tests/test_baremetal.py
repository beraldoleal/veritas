"""Unit tests for BaremetalExtractor."""

import hashlib

import pytest

from veritas.platforms.baremetal import BaremetalExtractor


def _make_extractor(**kwargs):
    defaults = dict(tee="tdx", ocp_versions=["4.21.0"])
    defaults.update(kwargs)
    return BaremetalExtractor(**defaults)


def _write_initdata(tmp_path, algorithm, name="initdata.toml"):
    content = f'algorithm = "{algorithm}"\nversion = "0.1.0"\n\n[data]\n'
    p = tmp_path / name
    p.write_text(content)
    return str(p), content.encode()


class TestComputeInitdata:
    def test_reads_sha256_from_header(self, tmp_path):
        path, content = _write_initdata(tmp_path, "sha256")
        extractor = _make_extractor()
        rv = extractor.compute_initdata([path])
        assert rv.algorithm == "sha256"
        assert rv.values == [hashlib.sha256(content).hexdigest()]

    def test_reads_sha384_from_header(self, tmp_path):
        path, content = _write_initdata(tmp_path, "sha384")
        extractor = _make_extractor()
        rv = extractor.compute_initdata([path])
        assert rv.algorithm == "sha384"
        assert rv.values == [hashlib.sha384(content).hexdigest()]

    def test_defaults_to_sha384_when_algorithm_missing(self, tmp_path):
        p = tmp_path / "initdata.toml"
        content = b'version = "0.1.0"\n\n[data]\n'
        p.write_bytes(content)
        extractor = _make_extractor()
        rv = extractor.compute_initdata([str(p)])
        assert rv.algorithm == "sha384"
        assert rv.values == [hashlib.sha384(content).hexdigest()]

    def test_multiple_files_same_algorithm(self, tmp_path):
        path1, content1 = _write_initdata(tmp_path, "sha256", "a.toml")
        path2, content2 = _write_initdata(tmp_path, "sha256", "b.toml")
        extractor = _make_extractor()
        rv = extractor.compute_initdata([path1, path2])
        assert rv.algorithm == "sha256"
        assert len(rv.values) == 2
        assert rv.values[0] == hashlib.sha256(content1).hexdigest()
        assert rv.values[1] == hashlib.sha256(content2).hexdigest()

    def test_name_and_category(self, tmp_path):
        path, _ = _write_initdata(tmp_path, "sha256")
        extractor = _make_extractor()
        rv = extractor.compute_initdata([path])
        assert rv.name == "init_data"
        assert rv.category == "configuration"
