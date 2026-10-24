"""Generates the synthetic screenshot fixtures and their labels.

Why these exist: the maintainer's real captures cannot be committed (they hold personal data)
and they are badly unbalanced for scoring: two thirds fall in `other`, three categories have no
example at all, and there is no duplicate pair anywhere. A model that answered "other" to
everything would score 67% on them.

This set is balanced across all ten categories and contains the cases the real set lacks: an
exact duplicate, a resized near-duplicate, and images that imitate sensitive content without
containing any real secret. Everything here is invented. No real card number, password, code,
person or address appears.

Run: python generate.py     (needs Pillow; `uv run --with pillow python generate.py` also works)
"""

import json
import pathlib
import random

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).parent
OUT = HERE / "images"
SEED = 20261024

# Colours
DARK_BG, DARK_FG, DARK_MUTED = (24, 26, 31), (233, 236, 241), (142, 148, 160)
LIGHT_BG, LIGHT_FG, LIGHT_MUTED = (250, 250, 252), (26, 28, 33), (110, 116, 128)
ACCENT = (56, 132, 255)
DANGER = (220, 68, 62)
OK = (46, 160, 90)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """A scalable font that exists on macOS, Linux and Windows runners alike."""
    candidates = (
        ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
        if bold
        else ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]
    )
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Pillow's bundled scalable fallback, so CI without system fonts still produces real text.
    return ImageFont.load_default(size=size)


def window(width: int, height: int, title: str, dark: bool = True) -> tuple[Image.Image, ImageDraw.ImageDraw, tuple]:
    """A plausible app window: title bar with traffic lights, then a content area."""
    bg, fg, muted = (DARK_BG, DARK_FG, DARK_MUTED) if dark else (LIGHT_BG, LIGHT_FG, LIGHT_MUTED)
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    bar = 38
    draw.rectangle([0, 0, width, bar], fill=tuple(min(255, c + 12) for c in bg))
    for index, colour in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([16 + index * 20, 14, 26 + index * 20, 24], fill=colour)
    draw.text((width // 2, bar // 2), title, font=font(13), fill=muted, anchor="mm")
    return image, draw, (bg, fg, muted)


def lines(draw, x, y, rows, step=26):
    """Draws (text, font, colour) rows and returns the y after them."""
    for text, fnt, colour in rows:
        draw.text((x, y), text, font=fnt, fill=colour)
        y += step
    return y


SPECS = []


def spec(name, category, sensitive=False, pii=False, expiry="none", dup_group=None, note=""):
    def register(fn):
        SPECS.append((name, category, sensitive, pii, expiry, dup_group, note, fn))
        return fn
    return register


# ---------------------------------------------------------------- receipts
@spec("receipt-grocery", "receipt", note="Grocery till receipt with line items and a total.")
def _(p):
    img, d, (bg, fg, muted) = window(620, 560, "Receipt.pdf", dark=False)
    y = lines(d, 40, 70, [
        ("NORTHGATE MARKET", font(22, True), fg),
        ("14 Mill Road  ·  Tue 11 Aug 2026  19:42", font(13), muted),
    ])
    d.line([40, y + 6, 580, y + 6], fill=(220, 220, 226))
    y += 24
    for item, price in [("Oat milk 1L", "2.49"), ("Rye bread", "3.10"), ("Tomatoes 500g", "1.95"),
                        ("Cheddar 200g", "4.40"), ("Coffee beans", "8.25")]:
        d.text((40, y), item, font=font(15), fill=fg)
        d.text((580, y), price, font=font(15), fill=fg, anchor="ra")
        y += 28
    d.line([40, y + 6, 580, y + 6], fill=(220, 220, 226))
    d.text((40, y + 24), "TOTAL", font=font(18, True), fill=fg)
    d.text((580, y + 24), "20.19", font=font(18, True), fill=fg, anchor="ra")
    d.text((40, y + 70), "VISA ending 0000   ·   APPROVED", font=font(13), fill=muted)
    img.save(p)


@spec("receipt-order-confirm", "receipt", note="Online order confirmation with an order number and total.")
def _(p):
    img, d, (bg, fg, muted) = window(820, 480, "Order confirmed", dark=False)
    lines(d, 44, 76, [
        ("Thanks! Your order is confirmed.", font(24, True), fg),
        ("Order SG-4417-22   ·   placed 3 Sep 2026", font(14), muted),
        ("", font(10), muted),
        ("1 x Desk lamp, matte black          49.00", font(16), fg),
        ("1 x USB-C cable 2m                   12.50", font(16), fg),
        ("Shipping                              0.00", font(16), muted),
        ("Total                                61.50", font(18, True), fg),
    ], step=30)
    img.save(p)


@spec("receipt-restaurant", "receipt", note="Restaurant bill with a tip line.")
def _(p):
    img, d, (bg, fg, muted) = window(520, 600, "", dark=False)
    y = lines(d, 40, 70, [("CASA MIRANDA", font(21, True), fg), ("Table 7  ·  2 covers", font(13), muted)])
    y += 14
    for item, price in [("Tortilla espanola", "6.50"), ("Pulpo a la gallega", "14.00"),
                        ("Pan y alioli", "3.00"), ("Vino tinto (2)", "9.00")]:
        d.text((40, y), item, font=font(15), fill=fg)
        d.text((480, y), price, font=font(15), fill=fg, anchor="ra")
        y += 30
    d.text((40, y + 20), "Subtotal", font=font(15), fill=muted)
    d.text((480, y + 20), "32.50", font=font(15), fill=muted, anchor="ra")
    d.text((40, y + 50), "Total", font=font(19, True), fill=fg)
    d.text((480, y + 50), "32.50", font=font(19, True), fill=fg, anchor="ra")
    img.save(p)


# ------------------------------------------------------------ conversations
@spec("conversation-chat", "conversation", pii=True, note="Two-person chat thread with timestamps.")
def _(p):
    img, d, (bg, fg, muted) = window(640, 520, "Messages")
    y = 70
    thread = [("Are we still on for Thursday?", False), ("Yes! 7pm at the usual place", True),
              ("Perfect. I'll book a table", False), ("Great, see you then", True)]
    for text, mine in thread:
        w = 10 + int(d.textlength(text, font=font(15)))
        x0 = 620 - w - 20 if mine else 24
        d.rounded_rectangle([x0, y, x0 + w + 20, y + 44], radius=16,
                            fill=ACCENT if mine else (54, 58, 66))
        d.text((x0 + 16, y + 13), text, font=font(15), fill=(255, 255, 255))
        y += 58
    img.save(p)


@spec("conversation-email", "conversation", pii=True, note="Email thread with sender, subject and body.")
def _(p):
    img, d, (bg, fg, muted) = window(860, 520, "Inbox", dark=False)
    lines(d, 44, 72, [
        ("Re: Q3 handover notes", font(22, True), fg),
        ("Dana Whitfield  ·  to me  ·  Tue 09:14", font(13), muted),
        ("", font(8), muted),
        ("Hi, I've put the handover doc in the shared drive.", font(15), fg),
        ("The only open item is the vendor renewal, which", font(15), fg),
        ("needs a decision before the end of the month.", font(15), fg),
        ("", font(8), muted),
        ("Thanks,", font(15), fg),
        ("Dana", font(15), fg),
    ], step=27)
    img.save(p)


# ------------------------------------------------------------------- code
@spec("code-editor", "code", note="Code editor showing a Python function with line numbers.")
def _(p):
    img, d, (bg, fg, muted) = window(820, 520, "hashing.py — slothshot")
    code = [
        "def dhash(image: Image.Image) -> str:",
        '    """64-bit difference hash as 16 hex characters."""',
        '    small = image.convert("L").resize((9, 8))',
        "    pixels = small.tobytes()",
        "    bits = 0",
        "    for row in range(8):",
        "        offset = row * 9",
        "        for col in range(8):",
        "            bits <<= 1",
        "            if pixels[offset + col] > pixels[offset + col + 1]:",
        "                bits |= 1",
        '    return f"{bits:016x}"',
    ]
    for index, line in enumerate(code):
        d.text((26, 70 + index * 25), f"{index + 1:>3}", font=font(14), fill=(90, 96, 108))
        colour = (128, 203, 196) if line.strip().startswith(('"""', "#")) else DARK_FG
        d.text((70, 70 + index * 25), line, font=font(14), fill=colour)
    img.save(p)


@spec("code-terminal", "code", note="Terminal session running tests and printing a pass summary.")
def _(p):
    img, d, (bg, fg, muted) = window(760, 440, "zsh — 80x24")
    out = [("$ uv run pytest -q", DARK_FG), ("............                      [100%]", DARK_FG),
           ("12 passed in 0.48s", OK), ("", DARK_FG), ("$ uv run ruff check .", DARK_FG),
           ("All checks passed!", OK), ("$ ", DARK_FG)]
    for index, (line, colour) in enumerate(out):
        d.text((26, 70 + index * 26), line, font=font(15), fill=colour)
    img.save(p)


# ------------------------------------------------------- ticket or booking
@spec("ticket-boarding-past", "ticket or booking", pii=True, expiry="past",
      note="Boarding pass for a flight that has already departed.")
def _(p):
    img, d, (bg, fg, muted) = window(780, 420, "Boarding pass", dark=False)
    d.text((44, 70), "BOARDING PASS", font=font(14), fill=muted)
    d.text((44, 96), "MXP  →  LHR", font=font(38, True), fill=fg)
    lines(d, 44, 160, [
        ("Flight AZ-204   ·   Seat 14C   ·   Gate B7", font(16), fg),
        ("Departs  04 Feb 2026   07:25", font(16), fg),
        ("Passenger  SAMPLE / TRAVELLER", font(14), muted),
    ], step=30)
    d.rectangle([600, 150, 740, 290], fill=(20, 20, 20))
    img.save(p)


@spec("ticket-concert-future", "ticket or booking", expiry="future",
      note="Event ticket for a date still in the future.")
def _(p):
    img, d, (bg, fg, muted) = window(760, 420, "Ticket")
    d.text((44, 74), "THE PALE FOUNTAINS", font=font(30, True), fill=DARK_FG)
    lines(d, 44, 130, [
        ("Saturday 12 December 2026  ·  Doors 19:00", font(17), DARK_FG),
        ("Roundhouse, Camden  ·  Standing", font(16), DARK_MUTED),
        ("Order TKT-99120   ·   2 tickets", font(14), DARK_MUTED),
    ], step=32)
    img.save(p)


# --------------------------------------------------------------- documents
@spec("document-report", "document", note="Text document page with a heading and paragraphs.")
def _(p):
    img, d, (bg, fg, muted) = window(760, 640, "Annual review.docx", dark=False)
    y = lines(d, 50, 74, [("3. Operating summary", font(24, True), fg)], step=44)
    body = ["The second half of the year saw steady demand across all three",
            "regions, with the strongest growth in the northern territory.",
            "Headcount remained flat, and the cost base grew more slowly",
            "than revenue for the first time since 2023.",
            "",
            "Risks remain concentrated in a single supplier relationship,",
            "which the operations team is actively working to diversify."]
    for line in body:
        d.text((50, y), line, font=font(15), fill=fg)
        y += 26
    img.save(p)


@spec("document-invoice", "document", note="Invoice-style table with line items and a total.")
def _(p):
    img, d, (bg, fg, muted) = window(820, 500, "Invoice 2026-114", dark=False)
    d.text((44, 70), "4. Investment", font=font(24, True), fill=(31, 55, 92))
    d.rectangle([44, 116, 776, 152], fill=(31, 55, 92))
    d.text((56, 125), "Concept", font=font(15, True), fill=(255, 255, 255))
    d.text((764, 125), "Amount", font=font(15, True), fill=(255, 255, 255), anchor="ra")
    rows = [("Development and implementation (128 h)", "24,000.00"), ("Tax (16%)", "3,840.00")]
    y = 160
    for label, amount in rows:
        d.text((56, y), label, font=font(15), fill=fg)
        d.text((764, y), amount, font=font(15), fill=fg, anchor="ra")
        y += 34
    d.rectangle([44, y, 776, y + 36], fill=(232, 236, 244))
    d.text((56, y + 9), "Total", font=font(15, True), fill=fg)
    d.text((764, y + 9), "27,840.00", font=font(15, True), fill=fg, anchor="ra")
    img.save(p)


# ------------------------------------------------------------ social media
@spec("social-post", "social media", pii=True, note="Short social post with handle, likes and replies.")
def _(p):
    img, d, (bg, fg, muted) = window(640, 360, "")
    d.ellipse([28, 66, 76, 114], fill=(88, 96, 112))
    lines(d, 90, 70, [("Rowan Vale", font(17, True), DARK_FG), ("@rowanvale · 2h", font(14), DARK_MUTED)], step=24)
    d.text((28, 136), "spent an hour naming screenshots by hand today.", font=font(17), fill=DARK_FG)
    d.text((28, 162), "never again. building something about it.", font=font(17), fill=DARK_FG)
    d.text((28, 220), "   41 replies        312 reposts        2,104 likes", font=font(14), fill=DARK_MUTED)
    img.save(p)


@spec("social-profile", "social media", pii=True, note="Social profile header with follower counts.")
def _(p):
    img, d, (bg, fg, muted) = window(700, 420, "Profile")
    d.rectangle([0, 38, 700, 150], fill=(44, 62, 88))
    d.ellipse([34, 110, 134, 210], fill=(120, 130, 148), outline=DARK_BG, width=5)
    lines(d, 34, 226, [("Juniper Blake", font(22, True), DARK_FG), ("@juniperbuilds", font(15), DARK_MUTED),
                       ("Designer. Mostly typefaces.", font(15), DARK_FG),
                       ("892 following    4,410 followers", font(14), DARK_MUTED)], step=28)
    img.save(p)


# ------------------------------------------------------------------- memes
@spec("meme-macro", "meme", note="Image macro with impact-style caption text at top and bottom.")
def _(p):
    img = Image.new("RGB", (640, 640), (36, 38, 44))
    d = ImageDraw.Draw(img)
    random.seed(7)
    for _i in range(220):  # noisy "photo" so it does not read as a flat card
        x, y = random.randint(0, 640), random.randint(180, 470)
        r = random.randint(8, 48)
        g = random.randint(60, 150)
        d.ellipse([x, y, x + r, y + r], fill=(g, g - 12, g - 24))
    for text, y in [("WHEN YOU OPEN", 40), ("THE SCREENSHOTS FOLDER", 96)]:
        d.text((320, y), text, font=font(34, True), fill=(255, 255, 255), anchor="ma",
               stroke_width=3, stroke_fill=(0, 0, 0))
    d.text((320, 540), "4,812 FILES", font=font(40, True), fill=(255, 255, 255), anchor="ma",
           stroke_width=3, stroke_fill=(0, 0, 0))
    img.save(p)


@spec("meme-two-panel", "meme", note="Two-panel reaction meme with captions.")
def _(p):
    img = Image.new("RGB", (560, 620), (245, 245, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 560, 300], fill=(190, 198, 210))
    d.rectangle([0, 310, 560, 610], fill=(150, 185, 160))
    d.text((20, 20), "naming them one by one", font=font(26, True), fill=(20, 20, 20))
    d.text((20, 330), "letting it run overnight", font=font(26, True), fill=(20, 20, 20))
    for cx, cy in [(400, 170), (400, 480)]:
        d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill=(250, 220, 90), outline=(40, 40, 40), width=3)
    img.save(p)


# ------------------------------------------------------------------ design
@spec("design-canvas", "design", note="Design tool canvas with shapes, layers panel and a toolbar.")
def _(p):
    img, d, (bg, fg, muted) = window(900, 560, "Untitled — Design")
    d.rectangle([0, 38, 190, 560], fill=(32, 34, 40))
    for index, layer in enumerate(["Frame / Home", "  Hero", "  Card", "  Button", "Assets"]):
        d.text((16, 60 + index * 26), layer, font=font(13), fill=DARK_MUTED)
    d.rectangle([230, 90, 600, 300], fill=(68, 92, 160), outline=ACCENT, width=2)
    d.ellipse([640, 120, 790, 270], fill=(230, 120, 90))
    d.rounded_rectangle([230, 340, 460, 420], radius=14, fill=(240, 240, 245))
    for x in (230, 600):
        for y in (90, 300):
            d.rectangle([x - 4, y - 4, x + 4, y + 4], fill=(255, 255, 255), outline=ACCENT)
    img.save(p)


@spec("design-palette", "design", note="Colour palette sheet with swatches and hex values.")
def _(p):
    img, d, (bg, fg, muted) = window(760, 440, "Palette", dark=False)
    swatches = [("#1F2937", (31, 41, 55)), ("#3884FF", (56, 132, 255)), ("#2EA05A", (46, 160, 90)),
                ("#DC443E", (220, 68, 62)), ("#F4C542", (244, 197, 66))]
    for index, (label, colour) in enumerate(swatches):
        x = 44 + index * 140
        d.rounded_rectangle([x, 90, x + 118, 240], radius=12, fill=colour)
        d.text((x, 256), label, font=font(14), fill=fg)
    d.text((44, 330), "Brand palette  ·  v3", font=font(18, True), fill=fg)
    img.save(p)


# ---------------------------------------------------------- error messages
@spec("error-dialog", "error message", note="Modal error dialog with a message and buttons.")
def _(p):
    img, d, (bg, fg, muted) = window(640, 380, "", dark=False)
    d.rounded_rectangle([90, 90, 550, 310], radius=14, fill=(255, 255, 255), outline=(216, 216, 222))
    d.ellipse([120, 126, 164, 170], fill=DANGER)
    d.text((142, 148), "!", font=font(28, True), fill=(255, 255, 255), anchor="mm")
    lines(d, 184, 126, [("Could not save the file", font(19, True), fg),
                        ("The disk is full. Free up some space and", font(14), muted),
                        ("try again.", font(14), muted)], step=26)
    d.rounded_rectangle([404, 244, 520, 284], radius=8, fill=ACCENT)
    d.text((462, 264), "OK", font=font(15), fill=(255, 255, 255), anchor="mm")
    img.save(p)


@spec("error-stacktrace", "error message", note="Terminal showing an unhandled exception and traceback.")
def _(p):
    img, d, (bg, fg, muted) = window(860, 420, "zsh — error")
    out = [("$ uv run python -m app", DARK_FG),
           ("Traceback (most recent call last):", DANGER),
           ('  File "app/main.py", line 42, in create_app', DARK_FG),
           ("    engine = make_engine(settings.data_dir)", DARK_FG),
           ('  File "app/db.py", line 18, in make_engine', DARK_FG),
           ("    SQLModel.metadata.create_all(engine)", DARK_FG),
           ("sqlite3.OperationalError: unable to open database file", DANGER)]
    for index, (line, colour) in enumerate(out):
        d.text((24, 68 + index * 26), line, font=font(14), fill=colour)
    img.save(p)


@spec("error-404", "error message", note="Browser page showing a 404 not found error.")
def _(p):
    img, d, (bg, fg, muted) = window(820, 480, "Not found", dark=False)
    d.rounded_rectangle([20, 50, 800, 86], radius=8, fill=(238, 238, 243))
    d.text((36, 60), "https://example.invalid/missing-page", font=font(14), fill=muted)
    d.text((410, 210), "404", font=font(76, True), fill=(200, 204, 212), anchor="mm")
    d.text((410, 280), "This page could not be found.", font=font(19), fill=fg, anchor="mm")
    img.save(p)


# ------------------------------------------------------------------- other
@spec("other-settings", "other", note="Application settings panel with toggles.")
def _(p):
    img, d, (bg, fg, muted) = window(720, 460, "Settings")
    d.text((34, 66), "General", font=font(21, True), fill=DARK_FG)
    rows = [("Launch at login", True), ("Run only when idle", True),
            ("Pause on battery", True), ("Index sensitive text", False)]
    for index, (label, on) in enumerate(rows):
        y = 120 + index * 58
        d.text((34, y), label, font=font(16), fill=DARK_FG)
        d.rounded_rectangle([620, y - 4, 676, y + 24], radius=14, fill=OK if on else (80, 84, 94))
        cx = 662 if on else 634
        d.ellipse([cx - 11, y - 1, cx + 11, y + 21], fill=(255, 255, 255))
    img.save(p)


@spec("other-weather", "other", note="Weather widget showing a forecast.")
def _(p):
    img, d, (bg, fg, muted) = window(520, 400, "Weather", dark=False)
    d.text((40, 80), "Mexico City", font=font(20), fill=muted)
    d.text((40, 110), "21°", font=font(64, True), fill=fg)
    d.text((40, 196), "Partly cloudy  ·  H 24°  L 13°", font=font(15), fill=muted)
    for index, (day, temp) in enumerate([("Mon", "23°"), ("Tue", "22°"), ("Wed", "20°"), ("Thu", "24°")]):
        x = 40 + index * 112
        d.text((x, 250), day, font=font(14), fill=muted)
        d.text((x, 276), temp, font=font(18), fill=fg)
    img.save(p)


# -------------------------------------------------- sensitive (all invented)
@spec("sensitive-password-manager", "other", sensitive=True,
      note="Password manager entry with a revealed password. Invented credential.")
def _(p):
    img, d, (bg, fg, muted) = window(700, 440, "Vault")
    lines(d, 36, 72, [("staging-dashboard.invalid", font(20, True), DARK_FG),
                      ("Username", font(13), DARK_MUTED),
                      ("deploy-bot@example.invalid", font(16), DARK_FG),
                      ("Password", font(13), DARK_MUTED)], step=34)
    d.rounded_rectangle([36, 254, 420, 294], radius=8, fill=(44, 48, 56))
    d.text((48, 264), "hunter2-not-a-real-password", font=font(17), fill=DARK_FG)
    d.text((36, 320), "One-time code  ·  000000", font=font(15), fill=DARK_MUTED)
    img.save(p)


@spec("sensitive-card-form", "other", sensitive=True,
      note="Checkout form with a card number filled in. Invented test number.")
def _(p):
    img, d, (bg, fg, muted) = window(680, 460, "Checkout", dark=False)
    d.text((40, 70), "Payment details", font=font(22, True), fill=fg)
    fields = [("Card number", "4111 1111 1111 1111"), ("Name on card", "SAMPLE CARDHOLDER"),
              ("Expiry", "04 / 29"), ("CVC", "123")]
    y = 118
    for label, value in fields:
        d.text((40, y), label, font=font(13), fill=muted)
        d.rounded_rectangle([40, y + 20, 640, y + 58], radius=8, fill=(255, 255, 255),
                            outline=(214, 216, 222))
        d.text((52, y + 30), value, font=font(16), fill=fg)
        y += 82
    img.save(p)


@spec("sensitive-otp-sms", "conversation", sensitive=True,
      note="SMS containing a one-time verification code. Invented code.")
def _(p):
    img, d, (bg, fg, muted) = window(520, 400, "Messages")
    d.text((28, 66), "Bank (short code)", font=font(15), fill=DARK_MUTED)
    d.rounded_rectangle([24, 100, 460, 210], radius=16, fill=(54, 58, 66))
    lines(d, 44, 118, [("Your verification code is 482913.", font(16), DARK_FG),
                       ("It expires in 5 minutes. Do not share", font(16), DARK_FG),
                       ("it with anyone.", font(16), DARK_FG)], step=28)
    d.text((28, 230), "Today 14:02", font=font(13), fill=DARK_MUTED)
    img.save(p)


@spec("sensitive-bank-balance", "other", sensitive=True, pii=True,
      note="Banking screen showing an account number and balance. Invented account.")
def _(p):
    img, d, (bg, fg, muted) = window(640, 440, "Accounts", dark=False)
    d.text((40, 72), "Everyday account", font=font(20, True), fill=fg)
    d.text((40, 104), "Sort 00-00-00   ·   Acc 00000000", font=font(14), fill=muted)
    d.text((40, 150), "£2,418.77", font=font(42, True), fill=fg)
    d.line([40, 220, 600, 220], fill=(224, 226, 232))
    for index, (label, amount) in enumerate([("Card payment  ·  Northgate", "-20.19"),
                                             ("Salary", "+2,900.00"),
                                             ("Direct debit  ·  Energy", "-74.10")]):
        y = 240 + index * 44
        d.text((40, y), label, font=font(15), fill=fg)
        d.text((600, y), amount, font=font(15), fill=OK if amount.startswith("+") else fg, anchor="ra")
    img.save(p)


def main() -> None:
    random.seed(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    records = []

    for name, category, sensitive, pii, expiry, dup_group, note, fn in SPECS:
        path = OUT / f"{name}.png"
        fn(path)
        records.append(dict(file=path.name, category=category, sensitive=sensitive, pii=pii,
                            expiry=expiry, dup_group=dup_group, note=note))

    # The duplicate cases the real set has none of.
    exact_src = OUT / "receipt-grocery.png"
    exact_dst = OUT / "dup-exact-receipt-grocery.png"
    exact_dst.write_bytes(exact_src.read_bytes())
    records.append(dict(file=exact_dst.name, category="receipt", sensitive=False, pii=False,
                        expiry="none", dup_group="exact:receipt-grocery",
                        note="Byte-identical copy of receipt-grocery.png. Positive case for the "
                             "content hash; must be detected before any model runs."))

    near_src = OUT / "code-editor.png"
    near_dst = OUT / "dup-resized-code-editor.png"
    with Image.open(near_src) as im:
        im.resize((im.width // 2, im.height // 2), Image.Resampling.LANCZOS).save(near_dst)
    records.append(dict(file=near_dst.name, category="code", sensitive=False, pii=False,
                        expiry="none", dup_group="near:code-editor",
                        note="Same screenshot resaved at half size. Positive case for the perceptual "
                             "hash; the content hash will not catch it."))

    doc = {
        "schema_version": 1,
        "generated_by": "samples/synthetic/generate.py",
        "seed": SEED,
        "source": "Entirely invented. No real card number, password, verification code, person, "
                  "address or account appears in any of these images.",
        "categories": ["receipt", "conversation", "code", "ticket or booking", "document",
                       "social media", "meme", "design", "error message", "other"],
        "field_notes": {
            "sensitive": "Imitates the spec's list (passwords, card numbers, IDs, bank details, "
                         "verification codes) using invented values.",
            "pii": "Personal data that is not on that list (invented names and handles).",
            "expiry": "none | past | future.",
            "dup_group": "'exact:' and 'near:' groups are POSITIVE duplicate cases, unlike the "
                         "negative-only groups in the real set.",
        },
        "files": records,
    }
    (HERE / "expected-labels.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} images to {OUT} and expected-labels.json")


if __name__ == "__main__":
    main()
