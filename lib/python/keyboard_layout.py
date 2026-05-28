#!/usr/bin/env python3
"""
Keyboard layout viewer — Apple Compact keyboard (Mac Mini)
Layouts: French AZERTY · English QWERTY · Persian Standard
Supports: --auto to detect the current OS keyboard layout
"""
import argparse, sys, unicodedata, subprocess, platform

# ── ANSI ─────────────────────────────────────────────────────────────────────
R   = '\033[0m'
BLD = '\033[1m'
DIM = '\033[2m'
NRM = '\033[38;5;82m'    # bright green   — normal layer
SHF = '\033[38;5;220m'   # gold/yellow    — shift layer
OPT = '\033[38;5;87m'    # light cyan     — option/alt layer
HDR = '\033[38;5;141m'   # light purple   — header
BRD = '\033[38;5;239m'   # dark gray      — borders
HLT = '\033[38;5;196m'   # bright red     — highlight
WHT = '\033[38;5;255m'   # white

def c(text, col): return f"{col}{text}{R}"

# ── Key layout data: (normal, shift, option) ─────────────────────────────────
# French AZERTY — Apple Compact (Mac Mini)
FR_ROW1 = [
    ('²', '³', '—'),
    ('&', '1', '¹'),
    ('é', '2', '~'),
    ('"', '3', '#'),
    ("'", '4', '{'),
    ('(', '5', '['),
    ('-', '6', '|'),
    ('è', '7', '`'),
    ('_', '8', '\\'),
    ('ç', '9', '^'),
    ('à', '0', '@'),
    (')', '°', ']'),
    ('=', '+', '}'),
]
FR_ROW2 = [
    ('a', 'A', 'æ'),
    ('z', 'Z', 'Ω'),
    ('e', 'E', '€'),
    ('r', 'R', '®'),
    ('t', 'T', '†'),
    ('y', 'Y', '¥'),
    ('u', 'U', '·'),
    ('i', 'I', ''),
    ('o', 'O', 'œ'),
    ('p', 'P', 'π'),
    ('^', '¨', '¬'),
    ('$', '£', '¤'),
]
FR_ROW3 = [
    ('q', 'Q', ''),
    ('s', 'S', 'ß'),
    ('d', 'D', '∂'),
    ('f', 'F', 'ƒ'),
    ('g', 'G', ''),
    ('h', 'H', ''),
    ('j', 'J', ''),
    ('k', 'K', ''),
    ('l', 'L', ''),
    ('m', 'M', 'µ'),
    ('ù', '%', ''),
    ('*', 'µ', ''),
]
FR_ROW4 = [
    ('<', '>', '≤'),
    ('w', 'W', ''),
    ('x', 'X', '≈'),
    ('c', 'C', '©'),
    ('v', 'V', '√'),
    ('b', 'B', '∫'),
    ('n', 'N', ''),
    (',', '?', ''),
    (';', '.', '…'),
    (':', '/', '÷'),
    ('!', '§', ''),
]
FR_ROWS    = [FR_ROW1, FR_ROW2, FR_ROW3, FR_ROW4]
FR_INDENTS = [0, 4, 6, 8]

# English QWERTY — Apple (US layout)
EN_ROW1 = [
    ('`', '~', ''),
    ('1', '!', '¡'),
    ('2', '@', '€'),
    ('3', '#', '£'),
    ('4', '$', '¢'),
    ('5', '%', '∞'),
    ('6', '^', '§'),
    ('7', '&', '¶'),
    ('8', '*', '•'),
    ('9', '(', 'ª'),
    ('0', ')', 'º'),
    ('-', '_', '–'),
    ('=', '+', '≠'),
]
EN_ROW2 = [
    ('q', 'Q', 'œ'),
    ('w', 'W', '∑'),
    ('e', 'E', '´'),
    ('r', 'R', '®'),
    ('t', 'T', '†'),
    ('y', 'Y', '¥'),
    ('u', 'U', '¨'),
    ('i', 'I', 'ˆ'),
    ('o', 'O', 'ø'),
    ('p', 'P', 'π'),
    ('[', '{', '“'),
    (']', '}', '‘'),
    ('\\', '|', '«'),
]
EN_ROW3 = [
    ('a', 'A', 'å'),
    ('s', 'S', 'ß'),
    ('d', 'D', '∂'),
    ('f', 'F', 'ƒ'),
    ('g', 'G', '©'),
    ('h', 'H', '˙'),
    ('j', 'J', 'Δ'),
    ('k', 'K', '˚'),
    ('l', 'L', '¬'),
    (';', ':', '…'),
    ("'", '"', 'æ'),
]
EN_ROW4 = [
    ('z', 'Z', 'Ω'),
    ('x', 'X', '≈'),
    ('c', 'C', '©'),
    ('v', 'V', '√'),
    ('b', 'B', '∫'),
    ('n', 'N', '˜'),
    ('m', 'M', 'µ'),
    (',', '<', '≤'),
    ('.', '>', '≥'),
    ('/', '?', '÷'),
]
EN_ROWS    = [EN_ROW1, EN_ROW2, EN_ROW3, EN_ROW4]
EN_INDENTS = [0, 4, 6, 8]

# Persian — Standard Mac keyboard (Apple Persian)
# Tuple: (normal, shift)  — option layer = diacritics, shown only for common ones
FA_ROW1 = [
    ('۱', '!'), ('۲', '@'), ('۳', '#'), ('۴', '$'), ('۵', '%'),
    ('۶', '^'), ('۷', '&'), ('۸', '*'), ('۹', '('), ('۰', ')'),
    ('-', '_'), ('=', '+'),
]
FA_ROW2 = [
    ('ض', 'ٌ'),  # ض / tanvin damm
    ('ص', 'ٍ'),  # ص / tanvin kasr
    ('ث', 'ً'),  # ث / tanvin fath
    ('ق', 'ُ'),  # ق / damm
    ('ف', 'ِ'),  # ف / kasr
    ('غ', 'َ'),  # غ / fath
    ('ع', 'ّ'),  # ع / shadde
    ('ه', '‌'),  # ه / ZWNJ
    ('خ', '['),       # خ
    ('ح', ']'),       # ح
    ('ج', '{'),       # ج
    ('چ', '}'),       # چ
]
FA_ROW3 = [
    ('ش', 'ؤ'),  # ش / واو همزه
    ('س', 'ئ'),  # س / یاء همزه
    ('ی', 'ى'),  # ی / الف مقصوره
    ('ب', 'آ'),  # ب / الف مد
    ('ل', 'أ'),  # ل / الف همزه بالا
    ('ا', 'إ'),  # ا / الف همزه پایین
    ('ت', 'ة'),  # ت / تاء مربوطه
    ('ن', '،'),  # ن / ویرگول فارسی
    ('م', '«'),  # م / گیومه باز
    ('ک', '»'),  # ک / گیومه بسته
    ('گ', ':'),       # گ
]
FA_ROW4 = [
    ('ظ', '؟'),  # ظ / علامت سوال فارسی
    ('ط', 'ظ'),  # ط / ظ
    ('ز', 'ژ'),  # ز / ژ
    ('ر', 'ر'),  # ر
    ('ذ', 'ذ'),  # ذ
    ('د', 'د'),  # د
    ('پ', 'پ'),  # پ
    ('و', 'ؤ'),  # و / واو همزه
    (',', '>'),
    ('.', '.'),
    ('/', '÷'),
]
FA_ROWS    = [FA_ROW1, FA_ROW2, FA_ROW3, FA_ROW4]
FA_INDENTS = [0, 4, 6, 8]

# ── Auto-detect current keyboard layout ──────────────────────────────────────

def detect_system_layout():
    """
    Detect the active keyboard layout from the OS.
    Returns (lang_code, layout_name, source_description)
    """
    os_name = platform.system()

    if os_name == 'Darwin':
        try:
            # Query the active input source via defaults/plist
            result = subprocess.run(
                ['defaults', 'read', '/Library/Preferences/com.apple.HIToolbox',
                 'AppleSelectedInputSources'],
                capture_output=True, text=True, timeout=3
            )
            raw = result.stdout

            # Look for KeyboardLayout Name
            for line in raw.splitlines():
                if 'KeyboardLayout Name' in line or 'Input Mode' in line:
                    val = line.split('=')[-1].strip().strip(';').strip('"').strip("'")
                    val_lower = val.lower()
                    if any(k in val_lower for k in ['french', 'azerty', 'fr-']):
                        return ('fr', val, 'macOS HIToolbox')
                    if any(k in val_lower for k in ['persian', 'farsi', 'arabic']):
                        return ('fa', val, 'macOS HIToolbox')
                    if any(k in val_lower for k in ['qwerty', 'abc', 'us', 'english']):
                        return ('en', val, 'macOS HIToolbox')

            # Fallback: try AppleCurrentKeyboardLayoutInputSourceID from NSUserDefaults
            result2 = subprocess.run(
                ['defaults', 'read', '-g', 'AppleCurrentKeyboardLayoutInputSourceID'],
                capture_output=True, text=True, timeout=3
            )
            src_id = result2.stdout.strip().lower()
            if 'french' in src_id or 'azerty' in src_id or '.fr' in src_id:
                return ('fr', src_id, 'macOS defaults')
            if 'persian' in src_id or 'arabic' in src_id or 'farsi' in src_id:
                return ('fa', src_id, 'macOS defaults')
            if 'qwerty' in src_id or '.abc' in src_id or 'us' in src_id:
                return ('en', src_id, 'macOS defaults')

        except Exception:
            pass

        # Last resort: check current locale
        lang = platform.mac_ver()[2] if platform.mac_ver()[2] else ''
        if 'fr' in lang.lower():
            return ('fr', 'locale-fr', 'macOS locale')

    elif os_name == 'Linux':
        try:
            result = subprocess.run(
                ['setxkbmap', '-query'],
                capture_output=True, text=True, timeout=3
            )
            for line in result.stdout.splitlines():
                if line.startswith('layout:'):
                    layout = line.split(':')[-1].strip().lower()
                    if 'fr' in layout:
                        return ('fr', f'XKB: {layout}', 'setxkbmap')
                    if 'ir' in layout or 'ara' in layout:
                        return ('fa', f'XKB: {layout}', 'setxkbmap')
                    return ('en', f'XKB: {layout}', 'setxkbmap')
        except Exception:
            pass

    return (None, 'unknown', 'detection failed')


# ── Renderer ─────────────────────────────────────────────────────────────────

def draw_row(keys, indent=0, highlight=None, three_layer=True):
    """
    Draw one keyboard row.
    keys = list of (nrm, shf, opt) or (nrm, shf)
    Each key cell: 5 chars wide (3 inside + 2 borders).
    """
    pad = ' ' * indent
    tops = []; layer1 = []; layer2 = []; bots = []

    for entry in keys:
        if len(entry) == 3:
            nrm, shf, opt = entry
        else:
            nrm, shf = entry
            opt = ''

        nrm = nrm or ' '
        shf = shf or ' '
        opt = opt or ' '

        tops.append(c('┌───┐', BRD))
        bots.append(c('└───┘', BRD))

        if three_layer:
            opt_s = c(opt, HLT + BLD if (highlight and opt == highlight) else OPT)
            shf_s = c(shf, HLT + BLD if (highlight and shf == highlight) else SHF)
            layer1.append(f"{c(chr(0x2502), BRD)}{opt_s}{shf_s} {c(chr(0x2502), BRD)}")
        else:
            shf_s = c(shf, HLT + BLD if (highlight and shf == highlight) else SHF)
            layer1.append(f"{c(chr(0x2502), BRD)} {shf_s} {c(chr(0x2502), BRD)}")

        nrm_col = HLT + BLD if (highlight and nrm == highlight) else NRM + BLD
        nrm_s = c(nrm, nrm_col)
        layer2.append(f"{c(chr(0x2502), BRD)} {nrm_s} {c(chr(0x2502), BRD)}")

    sep = ' '
    print(f"{pad}{sep.join(tops)}")
    print(f"{pad}{sep.join(layer1)}")
    print(f"{pad}{sep.join(layer2)}")
    print(f"{pad}{sep.join(bots)}")
    print()


def header(title, subtitle=''):
    w = 68
    print()
    print(c('=' * w, HDR))
    print(c(f'  [KB]  {title}', HDR + BLD))
    if subtitle:
        print(c(f'  {subtitle}', DIM))
    print(c('=' * w, HDR))
    print()


def legend_3():
    print(f"  {c('(opt) Option', OPT)}  {c('(shf) Shift', SHF)}  {c('Normal', NRM + BLD)}")
    print()


def legend_2():
    print(f"  {c('(shf) Shift', SHF)}  {c('Normal', NRM + BLD)}")
    print()


# ── Layout displays ──────────────────────────────────────────────────────────

def show_fr(highlight=None, auto_info=None):
    if auto_info:
        header(
            'AZERTY  --  Apple Compact  (Francais)',
            f'Auto-detected: {auto_info}  |  opt=Option  shf=Shift'
        )
    else:
        header(
            'AZERTY  --  Apple Compact  (Mac Mini)',
            'Top-left=Option  Top-right=Shift  Middle=Normal'
        )
    legend_3()

    row_labels = [
        '  [Num row]',
        '  [Tab row  ->]',
        '  [Caps row  caps]',
        '  [Shift row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(FR_ROWS, FR_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight)

    # Modifier bar
    print(c('  +----------------------------------------------------------+', BRD))
    print(c('  |', BRD)
          + f"  {c('Ctrl', DIM)}  {c('Opt', OPT)}  {c('Cmd', WHT)}"
          + f"  {c('            Space            ', DIM)}  "
          + f"{c('Cmd', WHT)}  {c('Opt', OPT)}  "
          + c('|', BRD))
    print(c('  +----------------------------------------------------------+', BRD))

    print()
    print(c('  -- Symboles frequents (Option) ---------------------------------', BRD))
    symbols = [
        ('{',   "Opt + '    (touche 4)       <- {  accolade ouverte"),
        ('}',   'Opt + =    (touche =)       <- }  accolade fermee'),
        ('[',   'Opt + (    (touche 5)       <- [  crochet ouvrant'),
        (']',   'Opt + )    (touche 0/deg)   <- ]  crochet fermant'),
        ('|',   'Opt + -    (touche 6)       <- |  pipe Unix'),
        ('~',   'Opt + e    (touche 2/e)     <- ~  HOME sur Mac/Linux  ** important **'),
        ('@',   'Opt + a    (touche a/0)     <- @  email, SSH'),
        ('#',   'Opt + "    (touche 3)       <- #  hashtag, commentaire Python/bash'),
        ('`',   'Opt + e    (touche 7)       <- `  backtick Markdown / shell'),
        ('\\',  'Opt + _    (touche 8)       <- \\  backslash'),
        ('^',   'Opt + c    (touche 9)       <- ^  caret regex / exposant'),
        ('€', 'Opt + e    (touche E)    <- euro'),
        ('©', 'Opt + c    (touche C)    <- copyright'),
        ('®', 'Opt + r    (touche R)    <- registered'),
    ]
    for sym, combo in symbols:
        hl_sym = (sym == highlight)
        sym_s = c(f' {sym} ', HLT + BLD) if hl_sym else c(f' {sym} ', NRM + BLD)
        print(f"    {sym_s}  {c(combo, WHT)}")
    print()


def show_en(highlight=None, auto_info=None):
    if auto_info:
        header(
            'QWERTY  --  Apple Compact  (English US)',
            f'Auto-detected: {auto_info}  |  opt=Option  shf=Shift'
        )
    else:
        header(
            'QWERTY  --  Apple Compact  (English US)',
            'Top-left=Option  Top-right=Shift  Middle=Normal'
        )
    legend_3()

    row_labels = [
        '  [Num row]',
        '  [Tab row  ->]',
        '  [Caps row  caps]',
        '  [Shift row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(EN_ROWS, EN_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight)

    print(c('  +----------------------------------------------------------+', BRD))
    print(c('  |', BRD)
          + f"  {c('Ctrl', DIM)}  {c('Opt', OPT)}  {c('Cmd', WHT)}"
          + f"  {c('            Space            ', DIM)}  "
          + f"{c('Cmd', WHT)}  {c('Opt', OPT)}  "
          + c('|', BRD))
    print(c('  +----------------------------------------------------------+', BRD))

    print()
    print(c('  -- Common Option combos ----------------------------------------', BRD))
    combos = [
        ('~',      'Opt + n  (then Space)  <- ~ home directory'),
        ('€', 'Opt + 2              <- euro'),
        ('©', 'Opt + g              <- copyright'),
        ('®', 'Opt + r              <- registered'),
        ('°', 'Opt + 0  (zero)      <- degree'),
        ('…', 'Opt + ;              <- ellipsis'),
        ('–', 'Opt + -              <- en-dash'),
        ('—', 'Opt + Shf + -        <- em-dash'),
        ('≠', 'Opt + =              <- not equal'),
        ('∞', 'Opt + 5              <- infinity'),
        ('÷', 'Opt + /              <- division'),
    ]
    for sym, combo in combos:
        hl_sym = (sym == highlight)
        sym_s = c(f' {sym} ', HLT + BLD) if hl_sym else c(f' {sym} ', NRM + BLD)
        print(f"    {sym_s}  {c(combo, WHT)}")
    print()


def show_fa(highlight=None, auto_info=None):
    if auto_info:
        header(
            'Persian Standard  --  Apple Compact  (Farsi)',
            f'Auto-detected: {auto_info}  |  shf=Shift  Middle=Normal'
        )
    else:
        header(
            'Persian Standard  --  Apple Compact',
            'Top=Shift  Middle=Normal  (Apple Persian layout)'
        )
    legend_2()

    row_labels = [
        '  [Num row  0-9]',
        '  [Top row  ->]',
        '  [Home row  caps]',
        '  [Bottom row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(FA_ROWS, FA_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight, three_layer=False)

    print()
    print(c('  -- Notable keys ------------------------------------------------', BRD))
    notes = [
        ('،', 'n          <- Virgule farsi (,)'),
        ('؟',  'Shf + z    <- Point interrogation farsi (?)'),
        ('«',  'Shf + m    <- Guillemet ouvrant (<<)'),
        ('»',  'Shf + k    <- Guillemet fermant (>>)'),
        ('‌',  'Shf + h    <- Demi-espace ZWNJ'),
        ('آ',  'Shf + b    <- Alef mad (aa)'),
        ('ی',  'i          <- Ya farsi'),
        ('ى',  'Shf + i    <- Alef maqsura (ya arabe)'),
    ]
    for sym, combo in notes:
        hl_sym = (sym == highlight)
        sym_s = c(f' {sym} ', HLT + BLD) if hl_sym else c(f' {sym} ', NRM + BLD)
        print(f"    {sym_s}  {c(combo, WHT)}")
    print()


# ── Find mode ────────────────────────────────────────────────────────────────

def find_char(target):
    """Search all layouts for a character and print where it is."""
    results = []

    all_layouts = [
        ('FR', 'AZERTY', FR_ROWS, True),
        ('EN', 'QWERTY', EN_ROWS, True),
        ('FA', 'Persian', FA_ROWS, False),
    ]
    layer_names = ['Normal', 'Shift', 'Option']
    modifier_map = {
        'Normal': '',
        'Shift':  'Shift + ',
        'Option': 'Option + ',
    }

    for lang, name, rows, three in all_layouts:
        for ri, row in enumerate(rows):
            for ki, entry in enumerate(row):
                layers = 3 if three else 2
                for li in range(layers):
                    if li < len(entry) and entry[li] == target:
                        base = entry[0]
                        layer = layer_names[li]
                        results.append((lang, name, ri + 1, ki + 1, base, layer))

    print()
    print(c(f"  [search]  Looking for: {c(target, NRM + BLD)}  (U+{ord(target):04X})", HDR + BLD))
    print(c(f"  {'─' * 50}", BRD))

    if not results:
        print(f"  {c('Not found', HLT)}  '{target}' not in any known layout")
        print()
        print(f"  {c('Tip:', DIM)}  Try:  {c('amir keyboard fr', WHT)}  and look at the Option row")
        print()
        return

    for lang, name, row_n, key_n, base_key, layer in results:
        mod = modifier_map[layer]
        row_label = ['Num', 'Tab', 'Home', 'Shift'][row_n - 1]
        print(f"  {c(lang, OPT + BLD)}  {c(name, DIM)}  "
              f"row {row_n} ({row_label})  pos {key_n}  ->  "
              f"{c(mod, SHF)}{c(base_key, NRM + BLD)}  [{layer}]")
    print()

    # Show the relevant keyboard highlighted
    if results:
        lang = results[0][0]
        print(c(f"  (showing {results[0][1]} layout with key highlighted)", DIM))
        if lang == 'FR':
            show_fr(highlight=target)
        elif lang == 'EN':
            show_en(highlight=target)
        else:
            show_fa(highlight=target)


# ── Auto mode ─────────────────────────────────────────────────────────────────

def show_auto():
    lang, layout_name, source = detect_system_layout()

    print()
    print(c('=' * 68, HDR))
    print(c('  [KB]  Auto-detect keyboard layout', HDR + BLD))
    print(c(f'  Source: {source}', DIM))
    print(c('=' * 68, HDR))

    if lang is None:
        print()
        print(c('  Could not detect keyboard layout automatically.', HLT))
        print()
        print(f"  Try specifying manually:")
        print(f"    {c('amir keyboard fr', NRM)}  (French AZERTY)")
        print(f"    {c('amir keyboard en', NRM)}  (English QWERTY)")
        print(f"    {c('amir keyboard fa', NRM)}  (Persian)")
        print()
        return

    auto_info = layout_name

    print(c(f'  Detected: {c(lang.upper(), NRM + BLD)}  --  {layout_name}', WHT))

    if lang == 'fr':
        show_fr(auto_info=auto_info)
    elif lang == 'en':
        show_en(auto_info=auto_info)
    elif lang == 'fa':
        show_fa(auto_info=auto_info)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog='amir keyboard',
        description='Show keyboard layouts for Apple Compact keyboard',
        add_help=False,
    )
    p.add_argument('lang', nargs='?', default='fr',
                   choices=['fr', 'en', 'fa', 'auto'],
                   help='Layout: fr (AZERTY) en (QWERTY) fa (Persian) auto (detect)')
    p.add_argument('--find', '-f', metavar='CHAR',
                   help='Find which key produces this character')
    p.add_argument('--auto', '-a', action='store_true',
                   help='Auto-detect current OS keyboard layout')
    p.add_argument('-h', '--help', action='store_true')

    args = p.parse_args()

    if args.help:
        print("""
  Usage:  amir keyboard [fr|en|fa|auto] [--find CHAR]

  Layouts:
    fr      French AZERTY  -- Apple Compact (Mac Mini)  (default)
    en      English QWERTY -- Apple
    fa      Persian Standard -- Apple
    auto    Auto-detect from OS (priority)

  Options:
    --auto / -a      Detect and show the active OS keyboard layout
    --find CHAR      Find which key produces this character
                     Example:  amir keyboard --find @

  Examples:
    amir keyboard           # French AZERTY (default)
    amir keyboard auto      # detect active layout from OS
    amir keyboard en        # English QWERTY
    amir keyboard fa        # Persian
    amir keyboard --find @  # find @ on all layouts
""")
        return

    if args.auto or args.lang == 'auto':
        show_auto()
        return

    if args.find:
        find_char(args.find)
        return

    dispatch = {'fr': show_fr, 'en': show_en, 'fa': show_fa}
    dispatch.get(args.lang, show_fr)()


if __name__ == '__main__':
    main()
