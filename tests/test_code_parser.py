"""Tests for code parser module"""
from core.code_parser import CodeParser


def test_count_lines():
    parser = CodeParser()
    code = """# Comment
def test():
    pass

"""
    counts = parser.count_lines(code)
    assert counts["total"] == 5
    assert counts["code"] > 0


def test_count_lines_blank_and_comment():
    parser = CodeParser()
    code = "x = 1\n\n# comment\ny = 2"
    counts = parser.count_lines(code)
    assert counts["blank"] >= 1
    assert counts["comment"] >= 1


def test_calculate_complexity_simple():
    parser = CodeParser()
    complexity = parser.calculate_complexity("x = 1", "python")
    assert complexity >= 1


def test_calculate_complexity_complex():
    parser = CodeParser()
    code = """
def complex_func(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                print(i)
    else:
        return None
"""
    complexity = parser.calculate_complexity(code, "python")
    assert complexity > 2


def test_parse_python_functions_classes():
    parser = CodeParser()
    code = """
def func1():
    pass

class Foo:
    def bar(self):
        return 1
"""
    structure = parser.parse_python(code)
    assert len(structure["functions"]) >= 1
    assert any(f["name"] == "func1" for f in structure["functions"])
    assert any(c["name"] == "Foo" for c in structure["classes"])


def test_parse_python_syntax_error():
    parser = CodeParser()
    code = "def broken(:\n    pass"
    structure = parser.parse_python(code)
    assert len(structure["syntax_errors"]) >= 1
    assert structure["functions"] == []


def test_parse_python_imports():
    parser = CodeParser()
    code = "import os\nfrom pathlib import Path"
    structure = parser.parse_python(code)
    assert "os" in structure["imports"]
    assert any("Path" in i for i in structure["imports"])


def test_extract_todo_fixme():
    parser = CodeParser()
    code = "# TODO: add validation\n# FIXME: fix this bug"
    todos = parser.extract_todo_fixme(code)
    assert len(todos) >= 2
    assert any(t["type"] == "TODO" for t in todos)


def test_discover_files(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("var x=1")
    (tmp_path / ".git").mkdir()
    (tmp_path / "data.bin").write_bytes(b"\x00\x01")

    parser = CodeParser()
    files = parser.discover_files(tmp_path)
    names = [f["path"] for f in files]
    assert "app.py" in names
    assert not any("node_modules" in n for n in names)
    assert not any("data.bin" in n for n in names)


def test_read_and_analyze_file(tmp_path):
    (tmp_path / "mod.py").write_text("def add(a, b):\n    return a + b")
    parser = CodeParser()
    files = parser.discover_files(tmp_path)
    assert files
    rec = files[0]
    parser.read_file(rec)
    assert rec["success"] is True
    assert "add" in rec["content"]

    parser.analyze_file(rec)
    assert "metrics" in rec
    assert "structure" in rec
    assert any(f["name"] == "add" for f in rec["structure"]["functions"])
