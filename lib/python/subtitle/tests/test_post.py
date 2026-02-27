"""
Comprehensive tests for Telegram post generation.

Covers:
  1.  _to_persian_digits — numeral conversion helper
  2.  _srt_duration_str  — duration string from SRT entries (Persian numerals)
  3.  _telegram_sections_complete — completeness validator
  4.  _sanitize_post — markdown stripping + 1024-char hard cap
  5.  _get_post_prompt (fa) — prompt contains required info
  6.  generate_posts with mocked LLM — full pipeline smoke test
  7.  Integration with real SRT file (Downloads folder)
  8.  Length constraint (≤ 1024 chars)
  9.  Subtitle-language line present in post
  10. Duration extracted in Persian numerals

Run with:
    python -m pytest lib/python/subtitle/tests/test_post.py -v
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# ── Resolve imports ──────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]   # …/lib/python/subtitle
sys.path.insert(0, str(_ROOT.parent.parent.parent))   # project root so imports work
sys.path.insert(0, str(_ROOT.parent))                  # …/lib/python

from subtitle.processor import SubtitleProcessor


# ─────────────────────────────────────────────────────────────────────────────
# 1.  _to_persian_digits
# ─────────────────────────────────────────────────────────────────────────────
class TestToPersianDigits(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(SubtitleProcessor._to_persian_digits(0), '۰')

    def test_single_digit(self):
        self.assertEqual(SubtitleProcessor._to_persian_digits(5), '۵')

    def test_two_digits(self):
        self.assertEqual(SubtitleProcessor._to_persian_digits(24), '۲۴')

    def test_three_digits(self):
        self.assertEqual(SubtitleProcessor._to_persian_digits(350), '۳۵۰')

    def test_string_input(self):
        self.assertEqual(SubtitleProcessor._to_persian_digits('35'), '۳۵')

    def test_no_arabic_digits_survive(self):
        result = SubtitleProcessor._to_persian_digits(1234567890)
        self.assertNotIn('1', result)
        self.assertNotIn('9', result)
        self.assertEqual(result, '۱۲۳۴۵۶۷۸۹۰')


# ─────────────────────────────────────────────────────────────────────────────
# 2.  _srt_duration_str
# ─────────────────────────────────────────────────────────────────────────────
def _entry(end_ts: str) -> list:
    """Helper: list of entries whose last end timestamp is end_ts."""
    return [{'start': '00:00:00,000', 'end': end_ts, 'text': 'x'}]


class TestSrtDurationStr(unittest.TestCase):
    # ── FA (default) ──────────────────────────────────────────────────────
    def test_empty_entries(self):
        self.assertEqual(SubtitleProcessor._srt_duration_str([]), '')

    def test_exact_minutes_no_seconds_fa(self):
        """secs < 30 → no seconds part, Persian numerals"""
        result = SubtitleProcessor._srt_duration_str(_entry('00:35:00,000'), lang='fa')
        self.assertEqual(result, '۳۵ دقیقه')

    def test_minutes_with_seconds_over_30_fa(self):
        """secs >= 30 → include seconds, Persian numerals"""
        result = SubtitleProcessor._srt_duration_str(_entry('00:24:50,260'), lang='fa')
        self.assertEqual(result, '۲۴ دقیقه و ۵۰ ثانیه')

    def test_seconds_under_30_not_shown_fa(self):
        result = SubtitleProcessor._srt_duration_str(_entry('00:12:25,000'), lang='fa')
        self.assertEqual(result, '۱۲ دقیقه')

    def test_hours_and_minutes_fa(self):
        result = SubtitleProcessor._srt_duration_str(_entry('01:05:30,000'), lang='fa')
        self.assertEqual(result, '۱ ساعت و ۵ دقیقه')

    def test_fa_default_lang_is_fa(self):
        """Default lang param must produce Persian output."""
        result = SubtitleProcessor._srt_duration_str(_entry('00:24:50,260'))
        self.assertEqual(result, '۲۴ دقیقه و ۵۰ ثانیه')

    def test_uses_persian_numerals_not_arabic_fa(self):
        for ts in ('00:05:00,000', '00:15:00,000'):
            result = SubtitleProcessor._srt_duration_str(_entry(ts), lang='fa')
            for digit in '0123456789':
                self.assertNotIn(digit, result, f"Arabic digit '{digit}' in FA '{result}'")

    # ── non-FA (DE, EN, …) ───────────────────────────────────────────────
    def test_exact_minutes_de(self):
        result = SubtitleProcessor._srt_duration_str(_entry('00:35:00,000'), lang='de')
        self.assertEqual(result, '35 min')

    def test_minutes_with_seconds_de(self):
        result = SubtitleProcessor._srt_duration_str(_entry('00:24:50,260'), lang='de')
        self.assertEqual(result, '24 min 50 sec')

    def test_hours_and_minutes_de(self):
        result = SubtitleProcessor._srt_duration_str(_entry('01:05:30,000'), lang='de')
        self.assertEqual(result, '1 hr 5 min')

    def test_non_fa_uses_arabic_numerals_only(self):
        """Non-FA output must not contain Persian-Indic digits."""
        for lang in ('de', 'en', 'fr', 'ar'):
            result = SubtitleProcessor._srt_duration_str(_entry('00:24:50,260'), lang=lang)
            for digit in '۰۱۲۳۴۵۶۷۸۹':
                self.assertNotIn(digit, result,
                                 f"Persian digit '{digit}' in lang={lang} output '{result}'")
            # Must contain plain digits
            self.assertTrue(any(d in result for d in '0123456789'),
                            f"No Arabic digits in lang={lang} output '{result}'")

    def test_ki_srt_file_duration_fa(self):
        """Integration: parse real KI SRT → Persian duration for FA post."""
        srt_path = (
            '/Users/su6i/Downloads/subtitle/'
            'KI-Entwickler-Peter_Steinberger_wechselt-zu-Open_AI-ZIB2_vom_16.02.2026_fa.srt'
        )
        if not os.path.exists(srt_path):
            self.skipTest('KI SRT file not found — skipping')
        proc = _make_processor()
        entries = proc.parse_srt(srt_path)
        result = SubtitleProcessor._srt_duration_str(entries, lang='fa')
        self.assertEqual(result, '۲۴ دقیقه و ۵۰ ثانیه')
        for digit in '0123456789':
            self.assertNotIn(digit, result)

    def test_ki_srt_file_duration_de(self):
        """Integration: parse real KI SRT → Latin duration for DE post."""
        srt_path = (
            '/Users/su6i/Downloads/subtitle/'
            'KI-Entwickler-Peter_Steinberger_wechselt-zu-Open_AI-ZIB2_vom_16.02.2026_de.srt'
        )
        if not os.path.exists(srt_path):
            self.skipTest('KI DE SRT file not found — skipping')
        proc = _make_processor()
        entries = proc.parse_srt(srt_path)
        result = SubtitleProcessor._srt_duration_str(entries, lang='de')
        self.assertIn('min', result)
        for digit in '۰۱۲۳۴۵۶۷۸۹':
            self.assertNotIn(digit, result)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  _telegram_sections_complete
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_ELON_POST = (
    "📽️ مصاحبه کامل ایلان ماسک در مجمع جهانی اقتصاد داووس ۲۰۲۶\n"
    "با زیرنویس فارسی و انگلیسی\n\n"
    "🔴 «می‌خوایم استارفلیت Star Trek رو واقعی بسازیم»\n\n"
    "ایلان ماسک در گفتگو با لری فینک در داووس ۲۰۲۶ از بزرگ‌ترین پروژه‌های موازی بشر حرف می‌زنه.\n\n"
    "🚨 نکات مهم:\n\n"
    "🔹 رقابت هوش مصنوعی: ماسک از وضعیت xAI و رقابت با OpenAI، Google می‌گه\n\n"
    "🔹 رباتیک در مقیاس صنعتی: پیش‌بینی تولید میلیونی ربات Optimus\n\n"
    "🔹 فضا و انرژی: چرا SpaceX و انرژی هسته‌ای رو باید همزمان دنبال کرد\n\n"
    "🔹 اعداد بزرگ: ماسک از ارقام و مقیاس‌هایی حرف می‌زنه که ذهن رو درگیر می‌کنه\n\n"
    "🔹 آینده تمدن: هدف نهایی — تبدیل بشر به یه تمدن چندسیاره‌ای\n\n"
    "✨ توی این مصاحبه، ماسک با صراحت از پروژه‌هایی حرف می‌زنه که باور داره آینده‌ی بشریت بهشون وابسته‌ست.\n\n"
    "📌 اگه می‌خواید بدونید ماسک الان روی چی کار می‌کنه، این ویدیو رو ببینید.\n\n"
    "⏱️ مدت: ۳۵ دقیقه\n\n"
    "#ElonMusk #WEF #Davos2026 #AI #SpaceX"
)


class TestTelegramSectionsComplete(unittest.TestCase):
    def _check(self, text):
        return SubtitleProcessor._telegram_sections_complete(text)

    def test_sample_elon_post_passes(self):
        """The canonical sample post must pass all section checks."""
        ok, missing = self._check(SAMPLE_ELON_POST)
        self.assertTrue(ok, f"Sample post failed validation: {missing}")
        self.assertEqual(missing, [])

    def test_empty_post_fails_all(self):
        ok, missing = self._check('')
        self.assertFalse(ok)
        self.assertGreaterEqual(len(missing), 6, "Expected at least 6 missing sections")

    def test_missing_title_icon(self):
        post = SAMPLE_ELON_POST.replace('📽️', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('📽️' in m for m in missing))

    def test_missing_red_circle(self):
        post = SAMPLE_ELON_POST.replace('🔴', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('🔴' in m for m in missing))

    def test_missing_siren(self):
        post = SAMPLE_ELON_POST.replace('🚨', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('🚨' in m for m in missing))

    def test_missing_sparkle(self):
        post = SAMPLE_ELON_POST.replace('✨', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('✨' in m for m in missing))

    def test_missing_pushpin(self):
        post = SAMPLE_ELON_POST.replace('📌', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('📌' in m for m in missing))

    def test_missing_timer(self):
        post = SAMPLE_ELON_POST.replace('⏱️', '').replace('⏱', '')
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('⏱️' in m for m in missing))

    def test_only_4_bullets_fails(self):
        # Remove one 🔹
        post = SAMPLE_ELON_POST.replace('🔹', '', 1)   # removes first occurrence
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('bullet' in m for m in missing))

    def test_missing_hashtags(self):
        post = '\n'.join(
            line for line in SAMPLE_ELON_POST.splitlines() if not line.startswith('#')
        )
        ok, missing = self._check(post)
        self.assertFalse(ok)
        self.assertTrue(any('hashtag' in m for m in missing))

    def test_current_ki_post_validation(self):
        """The KI-Entwickler post on disk must pass validation (regenerated post is complete)."""
        post_path = (
            '/Users/su6i/Downloads/subtitle/'
            'KI-Entwickler-Peter_Steinberger_wechselt-zu-Open_AI-ZIB2_vom_16.02.2026_fa_telegram.txt'
        )
        if not os.path.exists(post_path):
            self.skipTest('KI telegram post not found — skipping')
        with open(post_path, 'r', encoding='utf-8') as f:
            text = f.read()
        ok, missing = self._check(text)
        self.assertTrue(ok, f"KI telegram post failed validation: {missing}")


# ─────────────────────────────────────────────────────────────────────────────
# 4.  _sanitize_post
# ─────────────────────────────────────────────────────────────────────────────
class TestSanitizePost(unittest.TestCase):
    def _s(self, text):
        return SubtitleProcessor._sanitize_post(text, 'telegram')

    def test_strips_bold(self):
        self.assertEqual(self._s('**bold**'), 'bold')

    def test_strips_italic_double_underscore(self):
        self.assertEqual(self._s('__italic__'), 'italic')

    def test_strips_single_asterisk(self):
        self.assertEqual(self._s('*text*'), 'text')

    def test_strips_leading_hr(self):
        self.assertFalse(self._s('---\nhello').startswith('---'))

    def test_no_change_when_under_1024(self):
        text = 'أ' * 900
        self.assertEqual(self._s(text), text)

    def test_hard_cap_at_1024(self):
        text = 'أ' * 1200
        result = self._s(text)
        self.assertLessEqual(len(result), 1024)

    def test_hard_cap_cuts_on_newline(self):
        # Build text with a newline just before 1024 to check smart cut
        prefix = 'أ' * 950
        suffix = '\n' + 'ب' * 100
        text = prefix + suffix
        result = self._s(text)
        self.assertLessEqual(len(result), 1024)

    def test_non_telegram_platform_unchanged(self):
        text = '**bold** content here'
        result = SubtitleProcessor._sanitize_post(text, 'youtube')
        # YouTube: return as-is (no stripping applied)
        self.assertEqual(result, text)


# ─────────────────────────────────────────────────────────────────────────────
# 5.  _get_post_prompt — content validation
# ─────────────────────────────────────────────────────────────────────────────
def _make_processor(api_key='test_key', google_api_key='test_gkey'):
    """Create a SubtitleProcessor without triggering heavy model loading."""
    proc = SubtitleProcessor.__new__(SubtitleProcessor)
    proc.api_key = api_key
    proc.google_api_key = google_api_key
    proc.logger = MagicMock()
    return proc


class TestGetPostPromptFa(unittest.TestCase):
    def setUp(self):
        self.proc = _make_processor()

    def _build(self, **kwargs):
        return self.proc._get_post_prompt(
            platform='telegram',
            title='KI Entwickler Peter Steinberger',
            srt_lang_name='فارسی',
            full_text='محتوای نمونه برای تست',
            srt_lang='fa',
            duration='۲۴ دقیقه و ۵۰ ثانیه',
            all_srt_langs=['de', 'fa'],
            source_lang='de',
            **kwargs,
        )

    def test_returns_system_and_user_tuple(self):
        system, user = self._build()
        self.assertIsInstance(system, str)
        self.assertIsInstance(user, str)
        self.assertGreater(len(system), 20)
        self.assertGreater(len(user), 50)

    def test_user_prompt_contains_title(self):
        _, user = self._build()
        self.assertIn('KI Entwickler Peter Steinberger', user)

    def test_user_prompt_contains_duration(self):
        _, user = self._build()
        self.assertIn('۲۴ دقیقه و ۵۰ ثانیه', user)

    def test_user_prompt_contains_subtitle_langs_in_farsi(self):
        _, user = self._build()
        self.assertIn('فارسی', user)
        self.assertIn('آلمانی', user)

    def test_user_prompt_contains_source_language_info(self):
        """Source language (video audio) must appear in the prompt."""
        _, user = self._build()
        self.assertIn('آلمانی', user)   # _src_info_fa = 'زبان ویدیو: آلمانی'

    def test_user_prompt_contains_subtitle_line(self):
        _, user = self._build()
        self.assertIn('با زیرنویس آلمانی و فارسی', user)

    def test_user_prompt_has_5_bullet_placeholders(self):
        _, user = self._build()
        # Template has 5 bullet placeholders; rules section also references 🔹
        # so total count must be at least 5
        self.assertGreaterEqual(user.count('🔹'), 5)

    def test_user_prompt_enforces_bullet_brevity(self):
        _, user = self._build()
        self.assertIn('۱۲', user)   # ≤۱۲ کلمه rule must appear

    def test_user_prompt_enforces_850_950_target(self):
        _, user = self._build()
        self.assertIn('۸۵۰', user)
        self.assertIn('۹۵۰', user)

    def test_user_prompt_has_duration_line_template(self):
        _, user = self._build()
        self.assertIn('⏱️', user)

    def test_unknown_platform_raises_valueerror(self):
        with self.assertRaises(ValueError):
            self.proc._get_post_prompt(
                platform='tiktok',
                title='title',
                srt_lang_name='فارسی',
                full_text='text',
            )


class TestGetPostPromptDe(unittest.TestCase):
    """Tests for the non-FA (e.g. German) Telegram prompt template."""

    def setUp(self):
        self.proc = _make_processor()

    def _build(self, **kwargs):
        return self.proc._get_post_prompt(
            platform='telegram',
            title='KI Entwickler Peter Steinberger',
            srt_lang_name='Deutsch',
            full_text='sample subtitle content',
            srt_lang='de',
            duration='24 min 50 sec',
            all_srt_langs=['de', 'fa'],
            source_lang='de',
            **kwargs,
        )

    def test_de_prompt_uses_film_strip_icon_not_camera(self):
        """DE template must use 📽️ (U+1F4FD) so _telegram_sections_complete passes."""
        _, user = self._build()
        self.assertIn('📽️', user)
        self.assertNotIn('🎥', user)

    def test_de_prompt_has_5_bullet_placeholders(self):
        _, user = self._build()
        self.assertGreaterEqual(user.count('🔹'), 5)

    def test_de_prompt_contains_duration(self):
        _, user = self._build()
        self.assertIn('24 min 50 sec', user)

    def test_de_prompt_contains_subtitle_line(self):
        _, user = self._build()
        self.assertIn('With German & Persian subtitles', user)

    def test_de_prompt_no_promotional_language(self):
        """System prompt must not use marketing words like 'catchy', 'engaging'."""
        system, _ = self._build()
        for word in ('catchy', 'engaging', 'creative writer', 'creative Telegram'):
            self.assertNotIn(word, system,
                             f"Promotional word '{word}' found in non-FA system prompt")

    def test_fa_prompt_no_promotional_language(self):
        """FA system prompt must be analytical, not promotional."""
        proc = _make_processor()
        system, _ = proc._get_post_prompt(
            platform='telegram',
            title='title',
            srt_lang_name='فارسی',
            full_text='text',
            srt_lang='fa',
        )
        for word in ('creative Telegram', 'creative writer', 'engaging'):
            self.assertNotIn(word, system,
                             f"Promotional word '{word}' found in FA system prompt")


# ─────────────────────────────────────────────────────────────────────────────
# 6.  generate_posts — mock LLM full pipeline
# ─────────────────────────────────────────────────────────────────────────────
COMPLETE_MOCK_POST = (
    "📽️ گفت‌وگوی اختصاصی با پیتر اشتاینبرگر، توسعه‌دهنده هوش مصنوعی\n"
    "با زیرنویس فارسی و آلمانی\n\n"
    "🔴 «دستیار من می‌تواند به جای من پشت کامپیوتر بنشیند و کارهای واقعی انجام دهد»\n\n"
    "پیتر اشتاینبرگر درباره انتقالش به اوپن‌ای‌آی صحبت می‌کند.\n\n"
    "🚨 نکات مهم:\n\n"
    "🔹 عامل‌های هوش مصنوعی: می‌تواند ایمیل بفرستد و کلیک کند\n\n"
    "🔹 کارهای پیچیده: رزرو سفر از پرواز تا بلیت موزه\n\n"
    "🔹 مرزهای اخلاقی: نگران استفاده در پایان‌نامه است\n\n"
    "🔹 مسئولیت‌پذیری: کاربر مسئول اقدامات عامل است\n\n"
    "🔹 آینده هوش مصنوعی: عامل‌ها جایگزین کارهای روزمره می‌شوند\n\n"
    "✨ این مصاحبه نشان می‌دهد هوش مصنوعی دیگر فقط متن نمی‌نویسد.\n\n"
    "📌 این ویدیو را تماشا کنید.\n\n"
    "⏱️ مدت: ۲۴ دقیقه و ۵۰ ثانیه\n\n"
    "#AI #OpenAI #PeterSteinberger #KI #AGI"
)

MINIMAL_SRT_CONTENT = """\
1
00:00:00,000 --> 00:00:05,000
محتوای نمونه

2
00:00:05,000 --> 00:24:50,260
پایان ویدیو
"""


class TestGeneratePostsMockLLM(unittest.TestCase):
    def setUp(self):
        self.proc = _make_processor()
        self.tmpdir = tempfile.mkdtemp()
        # Write minimal SRT
        self.srt_fa = os.path.join(self.tmpdir, 'video_fa.srt')
        self.srt_de = os.path.join(self.tmpdir, 'video_de.srt')
        with open(self.srt_fa, 'w', encoding='utf-8') as f:
            f.write(MINIMAL_SRT_CONTENT)
        with open(self.srt_de, 'w', encoding='utf-8') as f:
            f.write(MINIMAL_SRT_CONTENT)
        self.original_base = os.path.join(self.tmpdir, 'video')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_complete_post_saved(self):
        """Mock LLM returns a complete post → file must be saved."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        saved_path = saved['fa_telegram']
        self.assertTrue(os.path.exists(saved_path))
        with open(saved_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ok, missing = SubtitleProcessor._telegram_sections_complete(content)
        self.assertTrue(ok, f"Saved post is incomplete: {missing}")

    def test_saved_post_length_within_1024(self):
        """Saved post must not exceed Telegram's 1024-char caption limit."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertLessEqual(len(content), 1024,
                              f"Post is {len(content)} chars — exceeds 1024")

    def test_duration_in_post_is_persian(self):
        """The ⏱️ line in the saved post must use Persian-Indic numerals."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
            content = f.read()
        # Find the ⏱️ line
        dur_line = next((l for l in content.splitlines() if '⏱️' in l or '⏱' in l), None)
        self.assertIsNotNone(dur_line, "No ⏱️ duration line found in post")
        for digit in '0123456789':
            self.assertNotIn(digit, dur_line,
                             f"Arabic digit '{digit}' found in duration line: {dur_line!r}")

    def test_incomplete_llm_triggers_retry(self):
        """If LLM returns incomplete post, _call_llm_for_post must be called at least twice."""
        # Remove trailing-only sections (✨ 📌 ⏱️) — triggers tail-only append path
        incomplete = COMPLETE_MOCK_POST.replace('✨', '').replace('📌', '').replace('⏱️', '')
        # Also remove the hashtag line
        incomplete = '\n'.join(
            l for l in incomplete.splitlines() if not l.startswith('#')
        )
        TAIL = (
            "✨ این مصاحبه قابلیت‌های عامل‌های هوش مصنوعی را نشان می‌دهد.\n\n"
            "📌 برای علاقه‌مندان به توسعه هوش مصنوعی مفید است.\n\n"
            "⏱️ مدت: ۲۴ دقیقه و ۵۰ ثانیه\n\n"
            "#AI #OpenAI #KI #AGI #Automation"
        )
        call_count = {'n': 0}

        def mock_llm(system, user):
            call_count['n'] += 1
            if call_count['n'] == 1:
                return incomplete
            return TAIL   # append-only tail on retry

        self.proc._call_llm_for_post = mock_llm
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertGreaterEqual(call_count['n'], 2, "Retry was not triggered for incomplete post")

    def test_tail_truncation_retry_uses_append_message(self):
        """Tail-only truncation must send a 'continue/append' message, not a full rewrite."""
        incomplete_body = (
            "📽️ گفت‌وگو با توسعه‌دهنده هوش مصنوعی\n"
            "با زیرنویس فارسی و آلمانی\n\n"
            "🔴 «دستیار من می‌تواند کارهای واقعی انجام دهد»\n\n"
            "توضیح کوتاه.\n\n"
            "🚨 نکات مهم:\n\n"
            "🔹 موضوع اول: توضیح\n\n"
            "🔹 موضوع دوم: توضیح\n\n"
            "🔹 موضوع سوم: توضیح\n\n"
            "🔹 موضوع چهارم: توضیح\n\n"
            "🔹 موضوع پنجم: توضیح"  # ends here — ✨ 📌 ⏱️ hashtags missing
        )
        TAIL_RESPONSE = (
            "✨ موضوع اصلی این ویدیو.\n\n"
            "📌 برای علاقه‌مندان به هوش مصنوعی.\n\n"
            "⏱️ مدت: ۲۴ دقیقه و ۵۰ ثانیه\n\n"
            "#AI #OpenAI #KI #AGI #Automation"
        )
        received_users = []

        def mock_llm(system, user):
            received_users.append(user)
            if len(received_users) == 1:
                return incomplete_body
            return TAIL_RESPONSE

        self.proc._call_llm_for_post = mock_llm
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])

        # The retry prompt must say "continue" / "append" not "rewrite"
        self.assertGreaterEqual(len(received_users), 2)
        retry_msg = received_users[1]
        self.assertIn('TRUNCATED POST', retry_msg,
                      "Tail retry message must include the truncated post body")
        self.assertNotIn('Rewrite the COMPLETE post from scratch', retry_msg,
                         "Tail retry should NOT ask for a full rewrite")

        # The saved file must be complete (body + tail merged)
        self.assertIn('fa_telegram', saved)
        with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
            content = f.read()
        ok, missing = SubtitleProcessor._telegram_sections_complete(content)
        self.assertTrue(ok, f"Merged post failed validation: {missing}")

    def test_post_mentions_subtitle_languages(self):
        """Generated post must mention at least one subtitle language."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
            content = f.read()
        # Post should mention at least one of the language names
        lang_names = ['فارسی', 'آلمانی', 'انگلیسی', 'Persian', 'German']
        self.assertTrue(
            any(lang in content for lang in lang_names),
            f"Post doesn't mention any subtitle language: {content[:200]}"
        )

    def test_two_srt_langs_produce_two_posts(self):
        """With post_langs=['fa','de'], two output files must be produced."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa, 'de': self.srt_de}
        saved = self.proc.generate_posts(self.original_base, 'de', result,
                                         platforms=['telegram'], post_langs=['fa', 'de'])
        self.assertIn('fa_telegram', saved)
        self.assertIn('de_telegram', saved)

    def test_default_post_langs_is_fa_only(self):
        """Without post_langs, only FA post is generated even if DE SRT exists."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa, 'de': self.srt_de}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        self.assertNotIn('de_telegram', saved)

    def test_hashtags_present(self):
        """Post must contain at least 3 hashtags."""
        self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = {'fa': self.srt_fa}
        saved = self.proc.generate_posts(self.original_base, 'de', result, platforms=['telegram'])
        self.assertIn('fa_telegram', saved)
        with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
            content = f.read()
        import re
        hashtags = re.findall(r'#\w+', content)
        self.assertGreaterEqual(len(hashtags), 3, f"Only {len(hashtags)} hashtags found")

    def test_post_only_mode_skips_when_no_srt(self):
        """post_only=True with no SRT → returns empty dict without error."""
        proc = _make_processor()
        proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
        result = proc.run_workflow.__wrapped__ if hasattr(proc.run_workflow, '__wrapped__') else None
        # Call generate_posts directly with empty result and non-existent base
        saved = proc.generate_posts('/nonexistent/path/video', 'de', {}, platforms=['telegram'])
        self.assertEqual(saved, {})


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Integration: parse real SRT + build prompt
# ─────────────────────────────────────────────────────────────────────────────
class TestRealSrtIntegration(unittest.TestCase):
    SRT_FA = (
        '/Users/su6i/Downloads/subtitle/'
        'KI-Entwickler-Peter_Steinberger_wechselt-zu-Open_AI-ZIB2_vom_16.02.2026_fa.srt'
    )
    SRT_DE = (
        '/Users/su6i/Downloads/subtitle/'
        'KI-Entwickler-Peter_Steinberger_wechselt-zu-Open_AI-ZIB2_vom_16.02.2026_de.srt'
    )

    def setUp(self):
        if not os.path.exists(self.SRT_FA):
            self.skipTest('Real SRT files not found in ~/Downloads/subtitle/')
        self.proc = _make_processor()

    def test_parse_srt_returns_entries(self):
        entries = self.proc.parse_srt(self.SRT_FA)
        self.assertGreater(len(entries), 100, "Expected > 100 subtitle entries")

    def test_duration_uses_persian_numerals(self):
        entries = self.proc.parse_srt(self.SRT_FA)
        dur = SubtitleProcessor._srt_duration_str(entries)
        self.assertNotEqual(dur, '')
        for digit in '0123456789':
            self.assertNotIn(digit, dur, f"Arabic digit in duration: {dur!r}")

    def test_prompt_contains_subtitle_line(self):
        entries = self.proc.parse_srt(self.SRT_FA)
        dur = SubtitleProcessor._srt_duration_str(entries)
        _, user = self.proc._get_post_prompt(
            platform='telegram',
            title='KI Entwickler Peter Steinberger',
            srt_lang_name='فارسی',
            full_text='test',
            srt_lang='fa',
            duration=dur,
            all_srt_langs=['de', 'fa'],
            source_lang='de',
        )
        self.assertIn('با زیرنویس آلمانی و فارسی', user)

    def test_prompt_targets_900_char_range(self):
        entries = self.proc.parse_srt(self.SRT_FA)
        dur = SubtitleProcessor._srt_duration_str(entries)
        _, user = self.proc._get_post_prompt(
            platform='telegram',
            title='KI Entwickler',
            srt_lang_name='فارسی',
            full_text='test',
            srt_lang='fa',
            duration=dur,
            all_srt_langs=['de', 'fa'],
            source_lang='de',
        )
        # The prompt must mention the 850-950 character target
        self.assertIn('۸۵۰', user)
        self.assertIn('۹۵۰', user)

    def test_generate_posts_with_mock_uses_real_srt(self):
        """Full pipeline: real SRT → mock LLM → file saved and complete."""
        tmpdir = tempfile.mkdtemp()
        try:
            import shutil
            base = os.path.join(tmpdir, 'KI_video')
            shutil.copy(self.SRT_FA, base + '_fa.srt')
            if os.path.exists(self.SRT_DE):
                shutil.copy(self.SRT_DE, base + '_de.srt')

            self.proc._call_llm_for_post = MagicMock(return_value=COMPLETE_MOCK_POST)
            result = {'fa': base + '_fa.srt'}
            saved = self.proc.generate_posts(base, 'de', result, platforms=['telegram'])

            self.assertIn('fa_telegram', saved)
            with open(saved['fa_telegram'], 'r', encoding='utf-8') as f:
                content = f.read()

            ok, missing = SubtitleProcessor._telegram_sections_complete(content)
            self.assertTrue(ok, f"Post is not complete: {missing}")
            self.assertLessEqual(len(content), 1024)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
