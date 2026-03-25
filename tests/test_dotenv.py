from pathlib import Path
import tempfile
import unittest

from multiversal_pictures.dotenv import _parse_line, load_dotenv


class ParseLineTests(unittest.TestCase):
    def test_parses_export_and_quotes(self) -> None:
        self.assertEqual(_parse_line('export OPENAI_API_KEY="abc123"'), ("OPENAI_API_KEY", "abc123"))

    def test_ignores_invalid_or_comment_lines(self) -> None:
        self.assertIsNone(_parse_line("# comment"))
        self.assertIsNone(_parse_line("INVALID LINE"))
        self.assertIsNone(_parse_line("1INVALID=value"))


class LoadDotenvTests(unittest.TestCase):
    def test_loads_keys_without_overwriting_existing_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            env_path = root / ".env"
            env_path.write_text("A=1\nB=2\n", encoding="utf-8")

            import os

            original_a = os.environ.get("A")
            original_b = os.environ.get("B")
            os.environ["A"] = "already-set"
            try:
                result = load_dotenv(root)
                self.assertTrue(result.loaded)
                self.assertEqual(result.path, env_path)
                self.assertEqual(result.keys, ["A", "B"])
                self.assertEqual(os.environ["A"], "already-set")
                self.assertEqual(os.environ.get("B"), "2")
            finally:
                if original_a is None:
                    os.environ.pop("A", None)
                else:
                    os.environ["A"] = original_a
                if original_b is None:
                    os.environ.pop("B", None)
                else:
                    os.environ["B"] = original_b


if __name__ == "__main__":
    unittest.main()
