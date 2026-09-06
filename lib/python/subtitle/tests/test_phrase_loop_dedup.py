import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]   # …/lib/python/subtitle
sys.path.insert(0, str(_ROOT.parent.parent.parent))
sys.path.insert(0, str(_ROOT.parent))

from subtitle.models.types import WordObj  # noqa: E402 -- must load after sys.path is patched above
from subtitle.processor import SubtitleProcessor  # noqa: E402 -- must load after sys.path is patched above


def _make_words(tokens: list[str], step: float = 0.3) -> list[WordObj]:
    return [
        WordObj(
            start=i * step,
            end=(i * step) + step,
            word=tok,
        )
        for i, tok in enumerate(tokens)
    ]


class TestPhraseLoopCollapsesHallucination(unittest.TestCase):
    def test_phrase_loop_collapses_hallucination(self):
        phrase = ["it's", "not", "a", "good", "thing."]
        words = _make_words(phrase * 15)
        result = SubtitleProcessor._collapse_phrase_loops(words)
        self.assertEqual(len(result), 5)
        self.assertEqual([w.word for w in result], phrase)
        for i in range(5):
            self.assertEqual(result[i].start, words[i].start)
            self.assertEqual(result[i].end, words[i].end)


class TestPhraseLoopKeepsLegitimateRepeat(unittest.TestCase):
    def test_phrase_loop_keeps_legitimate_repeat(self):
        phrase = ["we", "shall", "overcome"]
        words = _make_words(phrase * 3)
        result = SubtitleProcessor._collapse_phrase_loops(words)
        self.assertEqual(len(result), 9)
        self.assertEqual([w.word for w in result], phrase * 3)
        for i in range(len(words)):
            self.assertEqual(result[i].start, words[i].start)
            self.assertEqual(result[i].end, words[i].end)


class TestPhraseLoopEdgeCases(unittest.TestCase):
    def test_empty_list_returns_empty_list(self):
        result = SubtitleProcessor._collapse_phrase_loops([])
        self.assertEqual(result, [])

    def test_short_input_returned_unchanged(self):
        tokens = ["hello", "world"]
        words = _make_words(tokens)
        result = SubtitleProcessor._collapse_phrase_loops(words)
        self.assertEqual(result, words)


if __name__ == "__main__":
    unittest.main()
