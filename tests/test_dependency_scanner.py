"""Tests for dependency scanner"""
from core.dependency_scanner import DependencyScanner


def test_parse_requirements():
    scanner = DependencyScanner()
    parsed = scanner._parse_requirements(
        "flask==2.3.0\nrequests>=2.28\n# comment\ngunicorn"
    )
    assert parsed["count"] == 3
    assert "flask" in parsed["dependencies"]


def test_unpinned_dependency_flagged(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\nrequests==2.28.1\n")
    scanner = DependencyScanner()
    result = scanner.scan_repository(tmp_path)
    titles = [i["title"] for i in result["issues"]]
    assert any("Unpinned" in t for t in titles)


def test_cryptography_eol_flagged(tmp_path):
    (tmp_path / "requirements.txt").write_text("cryptography==2.8\n")
    scanner = DependencyScanner()
    result = scanner.scan_repository(tmp_path)
    assert any("cryptography" in i["title"] for i in result["issues"])


def test_package_json_reference(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"foo": "github.com/user/foo"}}')
    scanner = DependencyScanner()
    result = scanner.scan_repository(tmp_path)
    assert any("Non-reproducible" in i["title"] for i in result["issues"])


def test_no_fabricated_cves(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==2.3.0\n")
    scanner = DependencyScanner()
    result = scanner.scan_repository(tmp_path)
    assert not any("CVE" in i["title"] for i in result["issues"])
