#!/usr/bin/env python3
"""Finish profile.html title/label i18n for Phase 7."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "templates/profile/profile.html"
text = path.read_text(encoding="utf-8")

def esc(msg: str, ctx: str = "profile") -> str:
    return f'{{% filter escapejs %}}{{% trans "{msg}" context "{ctx}" %}}{{% endfilter %}}'

def t(msg: str, ctx: str = "profile") -> str:
    return f'{{% trans "{msg}" context "{ctx}" %}}'

def tc(msg: str) -> str:
    return f'{{% trans "{msg}" context "common" %}}'

def tco(msg: str) -> str:
    return f'{{% trans "{msg}" context "companies" %}}'

reps = [
    ('<td class="text-muted">Phone</td>', f'<td class="text-muted">{tc("Phone")}</td>'),
    ('title="2-100 characters. Letters, digits, spaces, and &amp; \' . , - ( ) only. Must contain at least one letter."',
     f'title="{esc("2-100 characters. Letters, digits, spaces, and & . , - ( ) only. Must contain at least one letter.")}"'),
    ('title="Letters, digits and the symbols - / . _ only (2-100 characters)."',
     f'title="{esc("Letters, digits and the symbols - / . _ only (2-100 characters).")}"'),
    ('title="Enter a valid domain like mycompany.com (letters, digits, hyphens and dots; must include a TLD)"',
     f'title="{esc("Enter a valid domain like mycompany.com (letters, digits, hyphens and dots; must include a TLD)")}"'),
    ('<label>Website</label>', f'<label>{tco("Website")}</label>'),
    ('title="Enter a valid URL like https://example.com (letters, digits, and - . _ / only in the path)."',
     f'title="{esc("Enter a valid URL like https://example.com (letters, digits, and - . _ / only in the path).")}"'),
    ('title="3-120 characters. Letters, digits, spaces and the symbols , . - / # only."',
     f'title="{esc("3-120 characters. Letters, digits, spaces and the symbols , . - / # only.")}"'),
    ('title="Letters, digits and the symbols - / and spaces (1-15 characters)."',
     f'title="{esc("Letters, digits and the symbols - / and spaces (1-15 characters).")}"'),
    ('title="2-60 letters (letters, spaces, hyphens, apostrophes and periods)."',
     f'title="{esc("2-60 letters (letters, spaces, hyphens, apostrophes and periods).")}"'),
    ('<label>Country <span class="text-danger">*</span></label>', f'<label>{tco("Country")} <span class="text-danger">*</span></label>'),
    ('<label>Postal Code</label>', f'<label>{tco("Postal Code")}</label>'),
    ('title="3-12 characters. Letters, digits, spaces and hyphens only."',
     f'title="{esc("3-12 characters. Letters, digits, spaces and hyphens only.")}"'),
    ('<label>Phone</label>', f'<label>{tc("Phone")}</label>'),
    ('title="Digits and + - ( ) spaces only (7-25 characters, 5-15 digits)."',
     f'title="{esc("Digits and + - ( ) spaces only (7-25 characters, 5-15 digits).")}"'),
    ('title="1-20 characters. Letters, digits, dots and hyphens only."',
     f'title="{esc("1-20 characters. Letters, digits, dots and hyphens only.")}"'),
    ('title="Letters, spaces, hyphens, apostrophes, periods (2-50 characters)."',
     f'title="{esc("Letters, spaces, hyphens, apostrophes, periods (2-50 characters).")}"'),
    ('<label>Country</label>', f'<label>{tc("Country")}</label>'),
]
for old, new in reps:
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print("profile.html titles/labels fixed")
