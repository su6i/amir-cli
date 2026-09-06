"""Regression test for the F821 bug in `detect_video_dimensions`.

`media_io.py` called `json.loads(...)` on the primary ffprobe-JSON code path
without ever importing the `json` module. The bare `except Exception: pass`
around that path silently swallowed the resulting `NameError`, so the
rotation-aware branch could never run -- every call fell through to the
CSV fallback, which does not know about rotation metadata at all. Rotated
video (e.g. a portrait phone recording tagged `rotate=90`) then got its
width/height reported un-swapped.

This test stubs `subprocess.run` to return the primary JSON payload with a
90-degree side_data rotation and asserts the swapped (display-correct)
dimensions come back -- which is only possible if the JSON path actually
executes instead of raising `NameError` and being swallowed.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]  # …/lib/python/subtitle
sys.path.insert(0, str(_ROOT.parent.parent.parent))
sys.path.insert(0, str(_ROOT.parent))

from subtitle.io.media_io import detect_video_dimensions  # noqa: E402


class _FakeCompletedProcess:
    def __init__(self, stdout: str):
        self.stdout = stdout


class TestDetectVideoDimensionsUsesJsonPath(unittest.TestCase):
    def test_rotated_video_dimensions_are_swapped_via_json_path(self):
        # Coded size 480x854 (portrait sensor layout) with a 90-degree
        # side_data rotation -- display size should come back as 854x480.
        payload = (
            '{"streams": [{"width": 480, "height": 854, "tags": {}, '
            '"side_data_list": [{"rotation": 90}]}]}'
        )

        with patch("subtitle.io.media_io.subprocess.run") as mock_run:
            mock_run.return_value = _FakeCompletedProcess(stdout=payload)
            w, h = detect_video_dimensions("fake.mp4")

        # Only reachable if `json.loads` executed without raising NameError.
        self.assertEqual((w, h), (854, 480))
        # Only the primary JSON-path ffprobe call should have been needed --
        # if the NameError bug were still present, execution would fall
        # through to the CSV fallback and call subprocess.run a second time.
        self.assertEqual(mock_run.call_count, 1)

    def test_non_rotated_video_dimensions_unchanged(self):
        payload = (
            '{"streams": [{"width": 1920, "height": 1080, "tags": {}, '
            '"side_data_list": []}]}'
        )

        with patch("subtitle.io.media_io.subprocess.run") as mock_run:
            mock_run.return_value = _FakeCompletedProcess(stdout=payload)
            w, h = detect_video_dimensions("fake.mp4")

        self.assertEqual((w, h), (1920, 1080))
        self.assertEqual(mock_run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
