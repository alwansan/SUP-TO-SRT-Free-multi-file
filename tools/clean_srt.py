#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


SOUND_PATTERN = re.compile(
    r"""
    ^\s*
    [
        \(
        \[
    ]
    \s*
    (?:
        music|
        musical|
        singing|
        sings|
        song|
        laugh(?:s|ing)?|
        laughter|
        crying|
        sobbing|
        sigh(?:s|ing)?|
        gasp(?:s|ing)?|
        groan(?:s|ing)?|
        scream(?:s|ing)?|
        yelling|
        shouting|
        whisper(?:s|ing)?|
        breathing|
        footsteps|
        footstep|
        door|
        doors|
        knock(?:s|ing)?|
        knocking|
        phone|
        telephone|
        bell|
        bells|
        beep(?:s|ing)?|
        beeps|
        buzz(?:s|ing)?|
        buzzing|
        crowd|
        applause|
        clapping|
        cheering|
        wind|
        rain|
        thunder|
        lightning|
        gunshot(?:s)?|
        gunfire|
        explosion(?:s)?|
        crash(?:es)?|
        squeak(?:s|ing)?|
        mouse\s+squeak(?:s)?|
        dog\s+bark(?:s|ing)?|
        barking|
        cat\s+meow(?:s|ing)?|
        meow(?:s|ing)?|
        roar(?:s|ing)?|
        growl(?:s|ing)?|
        growling|
        grunts?|
        [a-z]+
    )
    \s*
    [
        \]
        \)
    ]
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Character names that appear at the beginning of dialogue.
#
# Examples:
# FINN: Hey Jake!
# JAKE: What?
# BMO: Hello!
#
# Be conservative:
# - Only remove a name when it is at the beginning.
# - Require a colon.
# - Require a reasonably short name.
# - Do not touch ordinary sentences containing colons later.
NAME_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<name>
        [A-Z][A-Z0-9' ._-]{0,24}
    )
    \s*:\s*
    (?P<text>.+)
    $
    """,
    re.VERBOSE,
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


def parse_srt(text: str):
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    blocks = re.split(r"\n\s*\n", text.strip())

    entries = []

    for block in blocks:

        lines = block.split("\n")

        if len(lines) < 3:
            continue

        number = lines[0].strip()
        timing = lines[1].strip()
        subtitle_text = "\n".join(lines[2:]).strip()

        if not re.match(
            r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}",
            timing,
        ):
            continue

        entries.append(
            {
                "number": number,
                "timing": timing,
                "text": subtitle_text,
            }
        )

    return entries


def clean_sounds(text: str):
    lines = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        # Remove complete [ ... ] / ( ... ) sound-only subtitles.
        if SOUND_PATTERN.match(line):
            continue

        # Remove bracketed sound/effect descriptions inside dialogue.
        line = re.sub(
            r"\[[^\]]{1,100}\]",
            "",
            line,
        )

        line = re.sub(
            r"\([^)]{1,100}\)",
            lambda m: (
                ""
                if re.search(
                    r"(mouse|squeak|music|laugh|sound|noise|door|footstep|"
                    r"breath|scream|cry|gasp|groan|whisper|buzz|beep|"
                    r"applause|cheer|thunder|rain|wind|explosion)",
                    m.group(0),
                    re.IGNORECASE,
                )
                else m.group(0)
            ),
            line,
        )

        line = re.sub(r"[ \t]{2,}", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines)


def remove_character_names(text: str):
    lines = []

    for line in text.splitlines():

        match = NAME_PATTERN.match(line)

        if match:

            name = match.group("name").strip()
            remaining = match.group("text").strip()

            # Avoid removing things that look like normal uppercase
            # text with a colon.
            if len(name) <= 25 and remaining:
                line = remaining

        lines.append(line)

    return "\n".join(lines)


def fix_ocr(text: str):

    for pattern, replacement in OCR_REPLACEMENTS:
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    # Common OCR spacing problems.
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Space before punctuation.
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)

    return text.strip()


def normalize_text(text: str):
    return re.sub(
        r"\s+",
        " ",
        text.replace("\n", " ").strip(),
    ).casefold()


def remove_duplicate_entries(entries):

    result = []

    previous = None

    for entry in entries:

        current = (
            entry["timing"],
            normalize_text(entry["text"]),
        )

        if previous is not None and current == previous:
            continue

        result.append(entry)
        previous = current

    return result


def clean_entries(
    entries,
    remove_sounds=True,
    remove_names=True,
    remove_duplicates=True,
    fix_ocr_enabled=True,
):

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

        # If cleaning removed the entire subtitle,
        # skip the subtitle block.
        if not text:
            continue

        entry = dict(entry)
        entry["text"] = text

        cleaned.append(entry)

    if remove_duplicates:
        cleaned = remove_duplicate_entries(cleaned)

    # Renumber SRT entries sequentially.
    for index, entry in enumerate(cleaned, start=1):
        entry["number"] = str(index)

    return cleaned


def write_srt(entries, path: Path):

    output = []

    for entry in entries:

        output.append(
            f"{entry['number']}\n"
            f"{entry['timing']}\n"
            f"{entry['text']}"
        )

    content = "\n\n".join(output)

    if content:
        content += "\n"

    path.write_text(
        content,
        encoding="utf-8-sig",
    )


def main():

    parser = argparse.ArgumentParser(
        description="Clean OCR-generated SRT subtitles."
    )

    parser.add_argument(
        "file",
        help="SRT file to clean",
    )

    parser.add_argument(
        "--remove-sounds",
        default="true",
    )

    parser.add_argument(
        "--remove-names",
        default="true",
    )

    parser.add_argument(
        "--remove-duplicates",
        default="true",
    )

    parser.add_argument(
        "--fix-ocr",
        default="true",
    )

    args = parser.parse_args()

    path = Path(args.file)

    if not path.exists():
        raise SystemExit(
            f"File not found: {path}"
        )

    text = path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )

    entries = parse_srt(text)

    cleaned = clean_entries(
        entries,
        remove_sounds=args.remove_sounds.lower() == "true",
        remove_names=args.remove_names.lower() == "true",
        remove_duplicates=args.remove_duplicates.lower() == "true",
        fix_ocr_enabled=args.fix_ocr.lower() == "true",
    )

    write_srt(
        cleaned,
        path,
    )

    print(
        f"Cleaned: {path.name} "
        f"({len(entries)} → {len(cleaned)} subtitles)"
    )


if __name__ == "__main__":
    main()            continue

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
