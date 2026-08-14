"""Clean Markdown files by removing image tags and empty links.

- Reads all `*.md` files from `textbook_txt/`.
- Removes inline image tags `![alt](url)`, HTML `<img ...>` tags, reference-style image links,
  and empty links like `[text]()`.
- Removes reference definitions that point to image URLs.
- Writes cleaned files to `data/cleaned_text/` preserving filenames.

Usage:
    python -m scripts.clean_markdown
"""
import glob
import os
import re

INPUT_DIR = os.environ.get("TEXTBOOK_MD_DIR", "textbook_txt")
OUTPUT_DIR = os.environ.get("CLEANED_TEXT_DIR", "data/cleaned_text")

# Patterns to remove
INLINE_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]*\)")
HTML_IMG_RE = re.compile(r"<img[^>]*>")
# Reference-style image: ![alt][id]
REF_IMAGE_RE = re.compile(r"!\[[^\]]*\]\s*\[[^\]]*\]")
# Empty links like [text]() or [text](   )
EMPTY_LINK_RE = re.compile(r"\[[^\]]+\]\(\s*\)")
# Reference definitions: [id]: url (remove if url points to image-like extension)
REF_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)\s*$", re.MULTILINE)

# Common image extensions to detect in reference defs
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')


def clean_markdown_text(text: str) -> str:
    # Remove inline images and HTML <img>
    text = INLINE_IMAGE_RE.sub('', text)
    text = HTML_IMG_RE.sub('', text)
    text = REF_IMAGE_RE.sub('', text)
    text = EMPTY_LINK_RE.sub('', text)

    # Remove reference definitions that point to image files
    def _ref_def_repl(m):
        url = m.group(1)
        lower = url.lower()
        if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
            return ''
        return m.group(0)

    text = REF_DEF_RE.sub(_ref_def_repl, text)

    # Collapse multiple consecutive blank lines to a maximum of two
    text = re.sub(r"\n{3,}", '\n\n', text)

    # Strip leading/trailing whitespace
    return text.strip() + '\n'


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(INPUT_DIR, "*.md"))
    if not files:
        print(f"No markdown files found in {INPUT_DIR}")
        return

    for path in files:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        cleaned = clean_markdown_text(content)
        out_name = os.path.basename(path)
        out_path = os.path.join(OUTPUT_DIR, out_name)

        with open(out_path, 'w', encoding='utf-8') as outf:
            outf.write(cleaned)

        print(f"Cleaned: {path} -> {out_path}")

    print(f"Done. Cleaned files written to {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
