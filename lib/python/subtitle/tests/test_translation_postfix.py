"""Tests for translation.postfix native-line visibility policy."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from subtitle.io.srt_parser import parse_srt_file
from subtitle.translation.postfix import (
    _HIDDEN_NATIVE_CUE_MARKER,
    apply_final_target_text_fixes,
)


def _write_srt(path: str, rows):
    with open(path, "w", encoding="utf-8-sig") as f:
        for idx, (start, end, text) in enumerate(rows, 1):
            f.write(f"{idx}\n{start} --> {end}\n{text}\n\n")


class _StubProcessor:
    def __init__(self, native_target_lines: str):
        self.native_target_lines = native_target_lines
        self.logger = Mock()

    def parse_srt(self, srt_path: str):
        return parse_srt_file(srt_path)

    def fix_persian_text(self, text: str) -> str:
        return text


class TestNativeTargetLinePolicy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.src_srt = os.path.join(self.temp_dir, "sample_en.srt")
        self.tgt_srt = os.path.join(self.temp_dir, "sample_fa.srt")

        _write_srt(
            self.src_srt,
            [
                ("00:00:00,000", "00:00:01,000", "What happened?"),
                ("00:00:01,100", "00:00:02,500", "سلام، حالت چطوره؟"),
                ("00:00:02,600", "00:00:03,900", "I am fine."),
            ],
        )

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_hide_native_target_lines_sets_hidden_marker(self):
        _write_srt(
            self.tgt_srt,
            [
                ("00:00:00,000", "00:00:01,000", "چه اتفاقی افتاد؟"),
                ("00:00:01,100", "00:00:02,500", "سلام، حالت چطوره؟"),
                ("00:00:02,600", "00:00:03,900", "من خوبم."),
            ],
        )

        processor = _StubProcessor(native_target_lines="hide")
        apply_final_target_text_fixes(
            processor,
            source_lang="en",
            target_langs=["fa"],
            result={"en": self.src_srt, "fa": self.tgt_srt},
        )

        out = parse_srt_file(self.tgt_srt)
        self.assertEqual(out[1]["text"], _HIDDEN_NATIVE_CUE_MARKER)
        self.assertEqual(out[0]["text"], "چه اتفاقی افتاد؟")
        self.assertEqual(out[2]["text"], "من خوبم.")

    def test_off_alias_hides_native_target_lines(self):
        _write_srt(
            self.tgt_srt,
            [
                ("00:00:00,000", "00:00:01,000", "چه اتفاقی افتاد؟"),
                ("00:00:01,100", "00:00:02,500", "سلام، حالت چطوره؟"),
                ("00:00:02,600", "00:00:03,900", "من خوبم."),
            ],
        )

        processor = _StubProcessor(native_target_lines="off")
        apply_final_target_text_fixes(
            processor,
            source_lang="en",
            target_langs=["fa"],
            result={"en": self.src_srt, "fa": self.tgt_srt},
        )

        out = parse_srt_file(self.tgt_srt)
        self.assertEqual(out[1]["text"], _HIDDEN_NATIVE_CUE_MARKER)
        self.assertEqual(out[0]["text"], "چه اتفاقی افتاد؟")
        self.assertEqual(out[2]["text"], "من خوبم.")

    def test_keep_native_target_lines_restores_hidden_marker(self):
        _write_srt(
            self.tgt_srt,
            [
                ("00:00:00,000", "00:00:01,000", "چه اتفاقی افتاد؟"),
                ("00:00:01,100", "00:00:02,500", _HIDDEN_NATIVE_CUE_MARKER),
                ("00:00:02,600", "00:00:03,900", "من خوبم."),
            ],
        )

        processor = _StubProcessor(native_target_lines="keep")
        apply_final_target_text_fixes(
            processor,
            source_lang="en",
            target_langs=["fa"],
            result={"en": self.src_srt, "fa": self.tgt_srt},
        )

        out = parse_srt_file(self.tgt_srt)
        self.assertEqual(out[1]["text"], "سلام، حالت چطوره؟")
        self.assertEqual(out[0]["text"], "چه اتفاقی افتاد؟")
        self.assertEqual(out[2]["text"], "من خوبم.")

    def test_on_alias_restores_hidden_marker(self):
        _write_srt(
            self.tgt_srt,
            [
                ("00:00:00,000", "00:00:01,000", "چه اتفاقی افتاد؟"),
                ("00:00:01,100", "00:00:02,500", _HIDDEN_NATIVE_CUE_MARKER),
                ("00:00:02,600", "00:00:03,900", "من خوبم."),
            ],
        )

        processor = _StubProcessor(native_target_lines="on")
        apply_final_target_text_fixes(
            processor,
            source_lang="en",
            target_langs=["fa"],
            result={"en": self.src_srt, "fa": self.tgt_srt},
        )

        out = parse_srt_file(self.tgt_srt)
        self.assertEqual(out[1]["text"], "سلام، حالت چطوره؟")
        self.assertEqual(out[0]["text"], "چه اتفاقی افتاد؟")
        self.assertEqual(out[2]["text"], "من خوبم.")


if __name__ == "__main__":
    unittest.main()
