#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

# Only treat bracketed text as a removable effect when it contains a
# recognized sound/effect keyword. This avoids deleting legitimate [dialogue].
SOUND_WORDS = (
    r"music|musical|sing(?:ing|s)?|song|"
    r"laugh(?:s|ing)?|laughter|cry(?:ing)?|crying|sobbing|"
    r"sigh(?:s|ing)?|gasp(?:s|ing)?|groan(?:s|ing)?|"
    r"scream(?:s|ing)?|yell(?:ing)?|shout(?:ing)?|"
    r"whisper(?:s|ing)?|breath(?:ing)?|"
    r"footsteps?|door(?:s)?|knock(?:s|ing)?|"
    r"phone|telephone|bell(?:s)?|beep(?:s|ing)?|"
    r"buzz(?:s|ing)?|crowd|applause|clap(?:ping)?|cheer(?:ing)?|"
    r"wind|rain|thunder|lightning|gunshots?|gunfire|"
    r"explosion(?:s)?|crash(?:es)?|squeak(?:s|ing)?|"
    r"mouse\s+squeak(?:s)?|dog\s+bark(?:s|ing)?|barking|"
    r"cat\s+meow(?:s|ing)?|meow(?:s|ing)?|roar(?:s|ing)?|"
    r"growl(?:s|ing)?|grunt(?:s)?|noise|sound"
)

SOUND_ONLY = re.compile(
    rf"^\s*[\[(]\s*(?:{SOUND_WORDS})\s*[\])]\s*$",
    re.IGNORECASE,
)

BRACKETED_EFFECT = re.compile(
    rf"[\[(]\s*(?:{SOUND_WORDS})[^)\]]*[\])]",
    re.IGNORECASE,
)

# Conservative: only a short ALL-CAPS-style speaker label followed by a colon.
# This handles FINN:, JAKE:, BMO:, etc. It does not remove normal lowercase
# prose such as "Note: ..." and does not touch colons later in a sentence.
NAME_PATTERN = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z0-9' ._-]{0,24})\s*:\s*(?P<text>.+)\s*$"
)

OCR_REPLACEMENTS = [
    (r"\bI['’]m\b", "I'm"),
    (r"\bI['’]ll\b", "I'll"),
    (r"\bI['’]ve\b", "I've"),
    (r"\bcan['’]t\b", "can't"),
    (r"\bwon['’]t\b", "won't"),
    (r"\bdon['’]t\b", "don't"),
    (r"\bdoesn['’]t\b", "doesn't"),
    (r"\bdidn['’]t\b", "didn't"),
    (r"\bisn['’]t\b", "isn't"),
    (r"\baren['’]t\b", "aren't"),
    (r"\bwasn['’]t\b", "wasn't"),
    (r"\bweren['’]t\b", "weren't"),
    (r"\bwouldn['’]t\b", "wouldn't"),
    (r"\bshouldn['’]t\b", "shouldn't"),
    (r"\bcouldn['’]t\b", "couldn't"),
]

TIME_PATTERN = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*"
    r"\d{2}:\d{2}:\d{2},\d{3}(?:\s+.*)?$"
)


def parse_srt(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    entries = []

    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 3:
            continue

        timing_index = next(
            (i for i, line in enumerate(lines) if TIME_PATTERN.match(line.strip())),
            None,
        )
        if timing_index is None or timing_index + 1 >= len(lines):
            continue

        timing = lines[timing_index].strip()
        subtitle_text = "\n".join(lines[timing_index + 1:]).strip()

        entries.append({"timing": timing, "text": subtitle_text})

    return entries


def clean_sounds(text):
    output = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Entire subtitle line such as [ mouse squeaks ].
        if SOUND_ONLY.match(line):
            continue

        # Remove recognized effect descriptions embedded in dialogue.
        line = BRACKETED_EFFECT.sub("", line)
        line = re.sub(r"[ \t]{2,}", " ", line).strip()

        if line:
            output.append(line)

    return "\n".join(output)


def remove_character_names(text):
    lines = []

    for line in text.splitlines():
        m = NAME_PATTERN.match(line)
        if m:
            name = m.group("name").strip()
            remaining = m.group("text").strip()

            # Keep this conservative: short uppercase labels only.
            if 1 <= len(name) <= 25 and remaining and name.upper() == name:
                line = remaining

        lines.append(line)

    return "\n".join(lines)


def fix_ocr(text):
    for pattern, replacement in OCR_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def normalize_text(text):
    return re.sub(r"\s+", " ", text.replace("\n", " ").strip()).casefold()


def clean_entries(entries, remove_sounds, remove_names, remove_duplicates, fix_ocr_enabled):
    cleaned = []

    for entry in entries:
        text = entry["text"]

        if remove_sounds:
            text = clean_sounds(text)

        if remove_names:
            text = remove_character_names(text)

        if fix_ocr_enabled:
            text = fix_ocr(text)

        text = text.strip()
        if not text:
            continue

        cleaned.append({"timing": entry["timing"], "text": text})

    if remove_duplicates:
        result = []
        previous_text = None

        for entry in cleaned:
            current = normalize_text(entry["text"])
            if previous_text is not None and current == previous_text:
                continue
            result.append(entry)
            previous_text = current

        cleaned = result

    return cleaned


def write_srt(entries, path):
    blocks = []
    for i, entry in enumerate(entries, start=1):
        blocks.append(f"{i}\n{entry['timing']}\n{entry['text']}")

    content = "\n\n".join(blocks)
    if content:
        content += "\n"

    path.write_text(content, encoding="utf-8-sig")


def main():
    parser = argparse.ArgumentParser(description="Clean OCR-generated SRT subtitles.")
    parser.add_argument("file")
    parser.add_argument("--remove-sounds", default="true")
    parser.add_argument("--remove-names", default="true")
    parser.add_argument("--remove-duplicates", default="true")
    parser.add_argument("--fix-ocr", default="true")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8-sig", errors="replace")
    entries = parse_srt(text)

    cleaned = clean_entries(
        entries,
        remove_sounds=args.remove_sounds.lower() == "true",
        remove_names=args.remove_names.lower() == "true",
        remove_duplicates=args.remove_duplicates.lower() == "true",
        fix_ocr_enabled=args.fix_ocr.lower() == "true",
    )

    write_srt(cleaned, path)
    print(f"Cleaned: {path.name} ({len(entries)} → {len(cleaned)} subtitles)")


if __name__ == "__main__":
    main()
