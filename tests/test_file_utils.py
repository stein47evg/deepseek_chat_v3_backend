import os
import pytest
from app.utils.file_utils import safe_join, is_allowed_file, validate_file_size
from app.core.exceptions import InvalidPathError, FileTooLargeError
from app.core.config import settings


class TestFileUtils:

    def test_safe_join_valid(self):
        base = "/home/user/project"
        result = safe_join(base, "src/main.py")
        # Проверяем, что путь заканчивается на правильную часть (кросс-платформенно)
        assert "src/main.py" in result or "src\\main.py" in result

    def test_safe_join_invalid(self):
        base = "/home/user/project"
        with pytest.raises(InvalidPathError):
            safe_join(base, "../etc/passwd")

    def test_is_allowed_file(self):
        assert is_allowed_file("main.py") is True
        assert is_allowed_file("app.js") is True
        assert is_allowed_file("style.css") is True
        assert is_allowed_file("file.exe") is False
        assert is_allowed_file("image.png") is False

    def test_validate_file_size_ok(self):
        validate_file_size(b"small file")

    def test_validate_file_size_too_large(self):
        large_content = b"x" * (settings.MAX_FILE_SIZE + 1)
        with pytest.raises(FileTooLargeError):
            validate_file_size(large_content)
