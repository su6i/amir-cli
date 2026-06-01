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
    ('@', '#', '·'),   # @ key: opt=middle dot
    ('&', '1', '¹'),   # confirmed from viewer
    ('é', '2', 'ë'),   # confirmed by user
    ('"', '3', '"'),   # opt=" (right double quote)
    ("'", '4', '{'),   # confirmed
    ('(', '5', '['),   # confirmed
    ('-', '6', '«'),   # opt=« (not | as assumed)
    ('è', '7', 'ï'),   # opt=ï (not ` as assumed)
    ('_', '8', 'Ç'),   # opt=Ç (not \ as assumed)
    ('ç', '9', '∂'),   # opt=∂
    ('à', '0', '}'),   # opt=} (not @ — @ has own key)
    (')', '°', '¡'),   # opt=¡ (inverted !)
    ('=', '+', '—'),   # opt=— (em dash, not })
]
FR_ROW2 = [
    ('a', 'A', 'æ'),   # confirmed
    ('z', 'Z', 'Å'),   # dead ring key (pink in viewer)
    ('e', 'E', 'ê'),   # dead circumflex (pink in viewer)
    ('r', 'R', '®'),   # confirmed
    ('t', 'T', '†'),   # confirmed
    ('y', 'Y', 'Ú'),   # opt=Ú
    ('u', 'U', '°'),   # opt=° (degree)
    ('i', 'I', 'ï'),   # opt=ï
    ('o', 'O', 'œ'),   # confirmed
    ('p', 'P', 'π'),   # confirmed
    ('^', '¨', 'ô'),   # opt=ô
    ('$', '£', '€'),   # opt=€ (not ¤)
]
FR_ROW3 = [
    ('q', 'Q', '`'),   # dead grave (pink in viewer)
    ('s', 'S', 'Ò'),   # opt=Ò
    ('d', 'D', '∂'),   # confirmed
    ('f', 'F', 'ƒ'),   # confirmed
    ('g', 'G', 'ﬁ'),   # opt=fi ligature (U+FB01)
    ('h', 'H', 'Î'),   # opt=Î
    ('j', 'J', 'Ï'),   # opt=Ï
    ('k', 'K', 'È'),   # opt=È
    ('l', 'L', '¬'),   # opt=¬
    ('m', 'M', 'µ'),   # confirmed
    ('ù', '%', 'Ú'),   # opt=Ú
    ('*', 'µ', '@'),   # opt=@
]
FR_ROW4 = [
    ('<', '>', '≤'),   # confirmed
    ('w', 'W', '<'),   # opt=<
    ('x', 'X', '≈'),   # confirmed
    ('c', 'C', '©'),   # confirmed
    ('v', 'V', '◊'),   # opt=◊ (lozenge, not √)
    ('b', 'B', 'ß'),   # opt=ß (not ∫)
    ('n', 'N', '~'),   # confirmed by user
    (',', '?', '∞'),   # opt=∞
    (';', '.', '+'),   # opt=+
    (':', '/', '÷'),   # confirmed
    ('!', '§', '≠'),   # opt=≠
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

def draw_row(keys, indent=0, highlight=None, three_layer=True, layer='all'):
    """
    Draw one keyboard row.
    layer = 'all'    → 2-line key: opt+shf on top, normal on bottom (default)
    layer = 'normal' → 1-line key: only normal char, large + centred
    layer = 'shift'  → 1-line key: only shift char
    layer = 'opt'    → 1-line key: only option char
    """
    pad = ' ' * indent
    tops = []; mids = []; bot1s = []; bots = []
    B = chr(0x2502)  # │
    EMPTY = c('·', BRD)   # placeholder for empty option slot

    for entry in keys:
        if len(entry) == 3:
            nrm, shf, opt = entry
        else:
            nrm, shf = entry
            opt = ''

        nrm = nrm or ' '
        shf = shf or ' '
        opt_raw = opt  # keep original for empty check

        tops.append(c('┌─────┐', BRD))
        bots.append(c('└─────┘', BRD))

        if layer == 'all':
            if three_layer:
                opt_s = c(opt or ' ', HLT + BLD if (highlight and opt == highlight) else OPT)
                shf_s = c(shf, HLT + BLD if (highlight and shf == highlight) else SHF)
                mids.append(f"{c(B, BRD)}{opt_s}  {shf_s} {c(B, BRD)}")
            else:
                shf_s = c(shf, HLT + BLD if (highlight and shf == highlight) else SHF)
                mids.append(f"{c(B, BRD)}  {shf_s}  {c(B, BRD)}")
            nrm_col = HLT + BLD if (highlight and nrm == highlight) else NRM + BLD
            bot1s.append(f"{c(B, BRD)}  {c(nrm, nrm_col)}  {c(B, BRD)}")

        else:
            # single-layer mode: show one large character per key, centred
            if layer == 'shift':
                ch = shf
                col = SHF + BLD
            elif layer == 'opt':
                ch = opt_raw
                col = OPT + BLD
            else:  # normal
                ch = nrm
                col = NRM + BLD

            hl = highlight and ch == highlight
            if not ch:
                ch_s = EMPTY
            else:
                ch_s = c(ch, HLT + BLD if hl else col)
            mids.append(f"{c(B, BRD)}  {ch_s}  {c(B, BRD)}")
            bot1s.append(None)   # no second line in single-layer mode

    sep = ' '
    print(f"{pad}{sep.join(tops)}")
    print(f"{pad}{sep.join(mids)}")
    if any(x is not None for x in bot1s):
        print(f"{pad}{sep.join(bot1s)}")
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


def legend_layer(layer):
    labels = {
        'normal': f"  {c('[Normal]', NRM + BLD)}  — no modifier held",
        'shift':  f"  {c('[⇧ Shift]', SHF + BLD)}  — holding Shift",
        'opt':    f"  {c('[⌥ Option]', OPT + BLD)}  — holding Option",
    }
    print(labels.get(layer, ''))
    print()


def modifier_bar(layer='all'):
    """Bottom modifier key row, with the active modifier highlighted."""
    ctrl = c('Ctrl', DIM)
    opt_s  = c('Opt',  OPT + BLD if layer == 'opt'   else DIM)
    shf_s  = c('Shf',  SHF + BLD if layer == 'shift' else DIM)
    cmd  = c('Cmd',  DIM)
    spc  = c('            Space            ', DIM)
    print(c('  +----------------------------------------------------------+', BRD))
    print(c('  |', BRD) + f"  {ctrl}  {opt_s}  {cmd}  {spc}  {cmd}  {opt_s}  {shf_s} " + c('|', BRD))
    print(c('  +----------------------------------------------------------+', BRD))


# ── Layout displays ──────────────────────────────────────────────────────────

def show_fr(highlight=None, auto_info=None, layer='all'):
    subtitle_map = {
        'all':    'Top-left=Option  Top-right=Shift  Middle=Normal',
        'normal': 'Mode: Normal  (no modifier)',
        'shift':  'Mode: [holding Shift]',
        'opt':    'Mode: [holding Option]',
    }
    title = 'AZERTY  --  Apple Compact  (Mac Mini)'
    if auto_info:
        title = f'AZERTY  --  Apple Compact  (Francais)  [auto]'
    header(title, subtitle_map.get(layer, ''))

    if layer == 'all':
        legend_3()
    else:
        legend_layer(layer)

    row_labels = [
        '  [Num row]',
        '  [Tab row  ->]',
        '  [Caps row  caps]',
        '  [Shift row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(FR_ROWS, FR_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight, layer=layer)

    modifier_bar(layer)

    print()
    print(c('  -- Symboles frequents (Option) ---------------------------------', BRD))
    symbols = [
        ('{',   "Opt + '    (touche 4)         <- {  accolade ouverte"),
        ('}',   'Opt + à    (touche 0)         <- }  accolade fermee'),
        ('[',   'Opt + (    (touche 5)         <- [  crochet ouvrant'),
        ('«',   'Opt + -    (touche 6)         <- «  guillemet ouvrant'),
        ('~',   'Opt + n    (touche N) + Space <- ~  HOME Mac/Linux  *** dead key ***'),
        ('@',   'touche @   (1re touche)       <- @ direct, pas besoin Option !'),
        ('#',   'Shift + @  (1re touche)       <- # hashtag'),
        ('ë',   'Opt + e    (touche é/2)       <- e trema'),
        ('ï',   'Opt + i    (touche I)         <- i trema'),
        ('Ç',   'Opt + _    (touche 8)         <- C cedille majuscule'),
        ('—',   'Opt + =    (touche =)         <- — tiret long (em dash)'),
        ('€',   'Opt + $    (touche $)         <- euro'),
        ('©',   'Opt + c    (touche C)         <- copyright'),
        ('®',   'Opt + r    (touche R)         <- registered'),
        ('∂',   'Opt + d    (touche D)         <- derivee partielle'),
        ('∞',   'Opt + ,    (touche ,)         <- infini'),
    ]
    for sym, combo in symbols:
        hl_sym = (sym == highlight)
        sym_s = c(f' {sym} ', HLT + BLD) if hl_sym else c(f' {sym} ', NRM + BLD)
        print(f"    {sym_s}  {c(combo, WHT)}")
    print()


def show_en(highlight=None, auto_info=None, layer='all'):
    subtitle_map = {
        'all':    'Top-left=Option  Top-right=Shift  Middle=Normal',
        'normal': 'Mode: Normal  (no modifier)',
        'shift':  'Mode: [holding Shift]',
        'opt':    'Mode: [holding Option]',
    }
    title = 'QWERTY  --  Apple Compact  (English US)'
    if auto_info:
        title = f'QWERTY  --  Apple Compact  (English)  [auto]'
    header(title, subtitle_map.get(layer, ''))

    if layer == 'all':
        legend_3()
    else:
        legend_layer(layer)

    row_labels = [
        '  [Num row]',
        '  [Tab row  ->]',
        '  [Caps row  caps]',
        '  [Shift row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(EN_ROWS, EN_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight, layer=layer)

    modifier_bar(layer)

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


def show_fa(highlight=None, auto_info=None, layer='all'):
    subtitle_map = {
        'all':    'Top=Shift  Middle=Normal  (Apple Persian layout)',
        'normal': 'Mode: Normal  (no modifier)',
        'shift':  'Mode: [holding Shift]',
        'opt':    'Mode: [holding Option]',
    }
    header('Persian Standard  --  Apple Compact', subtitle_map.get(layer, ''))

    if layer == 'all':
        legend_2()
    else:
        legend_layer(layer)

    row_labels = [
        '  [Num row  0-9]',
        '  [Top row  ->]',
        '  [Home row  caps]',
        '  [Bottom row  shf]',
    ]
    for i, (row, indent) in enumerate(zip(FA_ROWS, FA_INDENTS)):
        print(c(row_labels[i], DIM))
        draw_row(row, indent=indent, highlight=highlight, three_layer=False,
                 layer='normal' if layer == 'opt' else layer)

    modifier_bar(layer)

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

    # Hint: full keyboard on demand
    if results:
        lang = results[0][0].lower()
        print(c(f"  tip: amir keyboard {lang} --opt   to see the full layout", DIM))
        print()


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
        show_fr(auto_info=auto_info, layer='all')
    elif lang == 'en':
        show_en(auto_info=auto_info, layer='all')
    elif lang == 'fa':
        show_fa(auto_info=auto_info, layer='all')


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
    p.add_argument('--shift', '-s', action='store_true',
                   help='Show keyboard with Shift held — what does each key produce?')
    p.add_argument('--opt', '-o', action='store_true',
                   help='Show keyboard with Option held — what does each key produce?')
    p.add_argument('--normal', '-n', action='store_true',
                   help='Show keyboard in normal mode (no modifier)')
    p.add_argument('-h', '--help', action='store_true')

    args = p.parse_args()

    if args.help:
        print("""
  Usage:  amir keyboard [fr|en|fa|auto] [--shift | --opt | --normal]

  Layouts:
    fr      French AZERTY  -- Apple Compact (Mac Mini)  (default)
    en      English QWERTY -- Apple
    fa      Persian Standard -- Apple
    auto    Auto-detect from OS

  Modifier view:
    --shift  / -s    Show what each key types when Shift is held
    --opt    / -o    Show what each key types when Option is held
    --normal / -n    Show normal layer only (no modifier)
    (default: show all 3 layers together)

  Other:
    --find CHAR      Find which key produces this character
    --auto / -a      Detect and show the active OS keyboard layout

  Examples:
    amir keyboard              # all layers (default)
    amir keyboard --shift      # Shift layer
    amir keyboard --opt        # Option layer
    amir keyboard fr --opt     # French + Option layer
    amir keyboard --find @     # find @ on all layouts
""")
        return

    # --find is independent: works with any lang or auto
    if args.find:
        find_char(args.find)
        return

    # resolve active layer
    if args.shift:
        layer = 'shift'
    elif args.opt:
        layer = 'opt'
    elif args.normal:
        layer = 'normal'
    else:
        layer = 'all'

    if args.auto or args.lang == 'auto':
        show_auto()
        return

    dispatch = {'fr': show_fr, 'en': show_en, 'fa': show_fa}
    fn = dispatch.get(args.lang, show_fr)
    fn(layer=layer)


if __name__ == '__main__':
    main()
