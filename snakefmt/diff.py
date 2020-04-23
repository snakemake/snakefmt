from typing import List
import difflib


class Diff:
    def __init__(self, compact: bool = True, context_lines: int = 3):
        self.compact = compact
        self.context_lines = context_lines

    @staticmethod
    def _splitlines(string: str) -> List[str]:
        return string.splitlines(keepends=True)

    def compare(self, original: str, new: str) -> str:
        original_lines = self._splitlines(original)
        new_lines = self._splitlines(new)

        if self.compact:
            diff = difflib.unified_diff(
                original_lines,
                new_lines,
                n=self.context_lines,
                fromfile="original",
                tofile="new",
            )
        else:
            diff = difflib.ndiff(original_lines, new_lines)

        return "".join(diff)
