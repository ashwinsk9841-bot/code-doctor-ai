"""Tests for security scanner module"""
from core.security_scanner import SecurityScanner, mask_secret


def test_scan_sql_injection_python():
    scanner = SecurityScanner()
    code = 'query = "SELECT * FROM users WHERE id = " + user_input'
    issues = scanner.scan_code(code, "python", path="a.py")
    assert any("sql" in i["title"].lower() or "statement" in i["title"].lower()
               for i in issues)


def test_scan_hardcoded_secrets():
    scanner = SecurityScanner()
    code = 'API_KEY = "sk-1234567890abcdefghijklmno"\npassword = "hunter22"'
    issues = scanner.scan_code(code, "python")
    assert len(issues) > 0
    output = " ".join(str(i.get("matched_secret")) for i in issues)
    # the long sk- key must be fully masked
    assert "sk-1234567890abcdefghijklmno" not in output
    assert output


def test_mask_secret():
    masked = mask_secret("sk-verylongsecretvalue", "OpenAI-style API key")
    assert "verylongsecretvalue" not in masked
    assert "********" in masked


def test_scan_eval_usage():
    scanner = SecurityScanner()
    code = "result = eval(user_input)\nvalue = exec(cmd)"
    issues = scanner.scan_code(code, "python")
    assert any("eval" in i["title"].lower() for i in issues)
    assert any("exec" in i["title"].lower() for i in issues)


def test_scan_safe_code():
    scanner = SecurityScanner()
    code = """
def add(a, b):
    return a + b
result = add(1, 2)
"""
    issues = scanner.scan_code(code, "python")
    assert not any(i["severity"] == "HIGH" for i in issues)


def test_scan_unsubprocess_shell_true():
    scanner = SecurityScanner()
    code = "subprocess.run(cmd, shell=True)"
    issues = scanner.scan_code(code, "python")
    assert any("shell" in i["title"].lower() for i in issues)


def test_scan_javascript_xss():
    scanner = SecurityScanner()
    code = "document.getElementById('o').innerHTML = userInput;"
    issues = scanner.scan_code(code, "javascript")
    assert any("xss" in i["title"].lower() or "innerhtml" in i["title"].lower()
               for i in issues)


def test_get_summary():
    scanner = SecurityScanner()
    issues = [
        {"severity": "HIGH"},
        {"severity": "HIGH"},
        {"severity": "MEDIUM"},
    ]
    summary = scanner.get_summary(issues)
    assert summary["total"] == 3
    assert summary["high"] == 2
    assert summary["medium"] == 1


def test_file_scan_integration(tmp_path):
    (tmp_path / "secret.py").write_text('AUTH_TOKEN = "sk-abcdefghijklmnopqrstuvwx"')
    from core.code_parser import CodeParser
    parser = CodeParser()
    files = parser.discover_files(tmp_path)
    parser.read_many(files)
    scanner = SecurityScanner()
    all_issues = scanner.scan_repository(files)
    assert any(i["severity"] == "HIGH" for i in all_issues)
