#!/usr/bin/env python3
"""
SRT cleaner.

- Removes standalone or inline bracketed sound/effect descriptions.
- Removes character names only at the start of a subtitle line, e.g.:
      FINN: Hello!
  ->  Hello!
- Removes exact consecutive duplicate subtitle blocks.
- Applies a few conservative OCR text fixes.
"""

from __future__ import annotations
import argparse
import re
from pathlib import Path

BRACKET_RE = re.compile(r"[\[(（【][^\]\)）】]{1,140}[\]\)）】]")

# Deliberately conservative. It only strips names when they occur at line start
# and are uppercase-ish, avoiding normal English text containing colons.
NAME_RE = re.compile(
    r"^\s*([A-Z][A-Z0-9'’.\-]*(?:\s+[A-Z][A-Z0-9'’.\-]*){0,3})\s*:\s+"
)

def bool_arg(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}

def read_srt(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")

def blocks(text: str):
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return re.split(r"\n{2,}", text) if text else []

def parse_block(block: str):
    lines = block.split("\n")
    if len(lines) < 3 or "-->" not in lines[1]:
        return None
    return lines[1].strip(), lines[2:]

def is_sound_description(text: str) -> bool:
    inner = text.strip()[1:-1].strip().lower()
    keywords = (
        "mouse squeak", "mouse squeaks", "squeak", "squeaks",
        "footstep", "footsteps", "laugh", "laughs", "laughing",
        "cry", "cries", "crying", "scream", "screams", "screaming",
        "shout", "shouts", "shouting", "whisper", "whispers",
        "whispering", "gasp", "gasps", "sigh", "sighs", "groan",
        "groans", "grunt", "grunts", "cough", "coughs", "sneeze",
        "sneezes", "breathing", "music", "noise", "sound", "sfx",
        "effect", "effects", "door", "doors",
    )
    return any(k in inner for k in keywords)

def clean_line(line: str, remove_sounds: bool, remove_names: bool, fix_ocr: bool):
    line = line.strip()
    if not line:
        return ""

    if remove_sounds:
        # Remove complete bracketed chunks. A cue that becomes empty is dropped.
        chunks = BRACKET_RE.findall(line)
        if chunks and all(is_sound_description(c) for c in chunks):
            line = BRACKET_RE.sub("", line)
        else:
            for c in chunks:
                if is_sound_description(c):
                    line = line.replace(c, "")
        line = re.sub(r"[ \t]{2,}", " ", line).strip()

    if remove_names:
        line = NAME_RE.sub("", line, count=1)

    if fix_ocr:
        line = line.replace("’", "'")
        line = re.sub(r"[ \t]+([,.!?;:])", r"\1", line)
        line = re.sub(r"([!?.,]){4,}", lambda m: m.group(0)[:3], line)

    return line.strip()

def process(path: Path, remove_sounds=True, remove_names=True,
            remove_duplicates=True, fix_ocr=True):
    output = []
    previous_text = None

    for block in blocks(read_srt(path)):
        parsed = parse_block(block)
        if not parsed:
            continue

        timing, text_lines = parsed
        cleaned_lines = [
            clean_line(line, remove_sounds, remove_names, fix_ocr)
            for line in text_lines
        ]
        cleaned_lines = [x for x in cleaned_lines if x]

        if not cleaned_lines:
            continue

        text = "\n".join(cleaned_lines)

        if (
            remove_duplicates
            and previous_text is not None
            and text.casefold() == previous_text.casefold()
        ):
            continue

        output.append(f"{len(output)+1}\n{timing}\n{text}")
        previous_text = text

    path.write_text(
        "\n\n".join(output) + ("\n\n" if output else ""),
        encoding="utf-8",
    )

def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--remove-sounds", default="true")
    p.add_argument("--remove-names", default="true")
    p.add_argument("--remove-duplicates", default="true")
    p.add_argument("--fix-ocr", default="true")
    a = p.parse_args()

    process(
        Path(a.file),
        bool_arg(a.remove_sounds),
        bool_arg(a.remove_names),
        bool_arg(a.remove_duplicates),
        bool_arg(a.fix_ocr),
    )

if __name__ == "__main__":
    main()
