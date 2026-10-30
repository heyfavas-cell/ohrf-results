import re
from pathlib import Path

from spikes.qopt_qaoa import folders

PACKAGE = Path(folders.__file__).parent


def test_ensure_dir_makes_nested_folders_returns_the_path_and_is_safe_to_repeat(tmp_path):
    target = tmp_path / "a" / "b" / "c"
    assert folders.ensure_dir(target) == target and target.is_dir()
    assert folders.ensure_dir(target) == target


def test_ensure_parent_makes_the_folder_a_file_will_go_in(tmp_path):
    file = tmp_path / "x" / "y" / "f.txt"
    assert folders.ensure_parent(file) == file and file.parent.is_dir() and not file.exists()


def test_write_text_creates_the_missing_folder_and_uses_unix_line_ends(tmp_path):
    file = folders.write_text(tmp_path / "n" / "f.txt", "a\nb\n")
    assert file.read_bytes() == b"a\nb\n"


def test_no_script_makes_folders_by_hand():
    offenders = [f"{p.name}:{n}" for p in sorted(PACKAGE.glob("*.py")) if p.name != "folders.py"
                 for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if re.search(r"\.mkdir\(|os\.makedirs\(", line)]
    assert offenders == []
