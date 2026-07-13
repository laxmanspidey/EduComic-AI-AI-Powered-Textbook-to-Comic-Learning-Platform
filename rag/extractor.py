"""
PDF text extraction using PyMuPDF (fitz).
Extracts text page-by-page and detects chapter boundaries using
3 progressive strategies:

  Strategy 1 — Regex patterns (handles: "Chapter N", "Unit N", "CHAPTER N", etc.)
  Strategy 2 — Font-size heading detection (finds large bold text = chapter titles)
  Strategy 3 — Auto-split by page count (for PDFs with no detectable headings)
"""
import re
import fitz  # PyMuPDF


# ──────────────────────────────────────────────────────────────────────────────
# Page text extraction
# ──────────────────────────────────────────────────────────────────────────────

def extract_text_by_pages(pdf_path: str) -> list[dict]:
    """
    Extract plain text from every page of a PDF.

    Returns:
        List of dicts: [{'page': 1, 'text': '...'}, ...]
    """
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            pages.append({
                'page': page_num + 1,
                'text': text.strip(),
            })
        doc.close()
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed: {e}") from e
    return pages


def extract_blocks_by_pages(pdf_path: str) -> list[dict]:
    """
    Extract text with font-size info from every page using PyMuPDF's dict mode.
    Used for heading detection (Strategy 2).

    Returns:
        List of dicts: [{'page': 1, 'blocks': [{'text': '...', 'size': 14.0, 'bold': True}, ...]}, ...]
    """
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            raw = page.get_text("dict")
            blocks_info = []
            for block in raw.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 0)
                        flags = span.get("flags", 0)
                        is_bold = bool(flags & 2**4)   # bit 4 = bold
                        is_upper = text.isupper() and len(text) > 4
                        if text:
                            blocks_info.append({
                                'text': text,
                                'size': size,
                                'bold': is_bold,
                                'upper': is_upper,
                            })
            pages.append({'page': page_num + 1, 'blocks': blocks_info})
        doc.close()
    except Exception:
        pass
    return pages


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 1: Regex-based chapter detection
# ──────────────────────────────────────────────────────────────────────────────

# Covers formats like:
#   Chapter 1: Title         Chapter 1 - Title
#   CHAPTER 1 TITLE          Unit 3: Algebra
#   Section 5 - Motion       Lesson 2: Forces
#   Part II - Mechanics      Module 4 Data Interpretation
#   1. Title                 1 TITLE (capital-only line after number)
_CHAPTER_PATTERNS = [
    # "Chapter/Unit/Section/Lesson/Module/Part N[: -] Title"
    re.compile(
        r'^(?:chapter|unit|section|lesson|module|part|topic)\s+(\d{1,3})\s*[:\-–—]?\s*(.{3,80})$',
        re.IGNORECASE | re.MULTILINE,
    ),
    # Roman numerals: "Chapter IV: Title"
    re.compile(
        r'^(?:chapter|unit|section|part)\s+(I{1,3}|IV|VI{0,3}|IX|XI{0,3}|XIV|XV|XVI{0,3}|XIX|XX)\s*[:\-–—]?\s*(.{3,80})$',
        re.IGNORECASE | re.MULTILINE,
    ),
    # Standalone numbered lines: "3. Quadratic Equations" or "3 QUADRATIC EQUATIONS"
    # Headings are short (<=8 words) — this is intentionally tighter than a
    # generic ".{3,70}" so it doesn't also match numbered body sentences like
    # "13.5 The energy U stored in a capacitor of capacitance C, with charge Q and..."
    re.compile(
        r'^(\d{1,2})\.\s+([A-Z][^.!?]{3,50})$',
        re.MULTILINE,
    ),
]

# Headings don't trail off with a connective word — a match ending in one of
# these is almost certainly a truncated body sentence, not a real heading.
_TRAILING_STOPWORDS = {
    'and', 'or', 'but', 'with', 'of', 'the', 'a', 'an', 'to', 'for', 'in',
    'on', 'at', 'is', 'are', 'was', 'were', 'by', 'as', 'that', 'which',
}


def _looks_like_real_heading(title_str: str) -> bool:
    """Heuristic filter to reject body-text sentences that match the numbered-line regex."""
    words = title_str.strip().split()
    if not words:
        return False
    if len(words) > 8:
        return False
    if words[-1].lower().strip(',.') in _TRAILING_STOPWORDS:
        return False
    # Real headings are rarely written entirely in lowercase words
    if title_str == title_str.lower():
        return False
    return True

def _roman_to_int(s: str) -> int:
    roman = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper()
    val = 0
    for i in range(len(s)):
        curr = roman.get(s[i], 0)
        nxt = roman.get(s[i+1], 0) if i + 1 < len(s) else 0
        val += curr if curr >= nxt else -curr
    return val


def _detect_by_regex(pages: list[dict]) -> list[dict]:
    chapters = []
    seen_nums = set()

    for page_info in pages:
        text = page_info['text']
        for pattern in _CHAPTER_PATTERNS:
            for match in pattern.finditer(text):
                num_str = match.group(1).strip()
                title_str = match.group(2).strip()[:200] if match.lastindex >= 2 else f'Chapter {num_str}'

                # Reject body-text sentences that happen to match the pattern
                # (e.g. a numbered equation or example that isn't really a heading)
                if not _looks_like_real_heading(title_str):
                    continue

                # Convert roman or arabic numeral
                try:
                    chapter_num = int(num_str)
                except ValueError:
                    try:
                        chapter_num = _roman_to_int(num_str)
                    except Exception:
                        continue

                if chapter_num <= 0 or chapter_num > 200:
                    continue
                if chapter_num in seen_nums:
                    continue

                seen_nums.add(chapter_num)
                chapters.append({
                    'number': chapter_num,
                    'title': title_str,
                    'page_start': page_info['page'],
                    'page_end': page_info['page'],
                })

    return chapters


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 2: Font-size heading detection
# ──────────────────────────────────────────────────────────────────────────────

def _detect_by_font_size(pdf_path: str, pages_text: list[dict]) -> list[dict]:
    """
    Detect chapters by finding the largest/boldest text on each page.
    Treats unusually large or all-caps bold text as a chapter heading.
    """
    block_pages = extract_blocks_by_pages(pdf_path)
    if not block_pages:
        return []

    # Compute median font size across all spans
    all_sizes = []
    for pg in block_pages:
        for b in pg['blocks']:
            all_sizes.append(b['size'])

    if not all_sizes:
        return []

    all_sizes.sort()
    median_size = all_sizes[len(all_sizes) // 2]
    heading_threshold = median_size * 1.35   # 35% larger than median = heading

    chapters = []
    chapter_num = 0
    seen_titles = set()

    for pg_info in block_pages:
        for block in pg_info['blocks']:
            text = block['text'].strip()
            size = block['size']
            is_bold = block['bold']
            is_upper = block['upper']

            # A heading candidate: large font OR (bold AND all-caps AND reasonable length)
            is_heading = (
                (size >= heading_threshold and len(text) > 4)
                or (is_bold and is_upper and 5 <= len(text) <= 80)
            )

            if not is_heading:
                continue

            # Skip page numbers, very short lines, pure numbers
            if re.match(r'^\d{1,4}$', text):
                continue
            if len(text) < 4:
                continue

            # Avoid duplicates
            canonical = re.sub(r'\s+', ' ', text.lower())[:60]
            if canonical in seen_titles:
                continue
            seen_titles.add(canonical)

            chapter_num += 1
            chapters.append({
                'number': chapter_num,
                'title': text[:200],
                'page_start': pg_info['page'],
                'page_end': pg_info['page'],
            })

    return chapters


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 3: Auto-split by page count
# ──────────────────────────────────────────────────────────────────────────────

_TOPIC_LABELS = [
    "Introduction", "Foundations", "Core Concepts", "Methods & Techniques",
    "Analysis", "Applications", "Advanced Topics", "Problem Solving",
    "Practice & Review", "Summary",
]

def _detect_by_split(total_pages: int, pages_per_chunk: int = 40) -> list[dict]:
    """
    Split the PDF into equal-sized chunks when no headings are found.
    For a 400-page book with pages_per_chunk=40 → 10 chapters.
    """
    chapters = []
    chapter_num = 0
    for start in range(1, total_pages + 1, pages_per_chunk):
        chapter_num += 1
        end = min(start + pages_per_chunk - 1, total_pages)
        label = _TOPIC_LABELS[chapter_num - 1] if chapter_num <= len(_TOPIC_LABELS) else f'Section {chapter_num}'
        chapters.append({
            'number': chapter_num,
            'title': f'{label} (Pages {start}–{end})',
            'page_start': start,
            'page_end': end,
        })
    return chapters


# ──────────────────────────────────────────────────────────────────────────────
# Main detect_chapters function
# ──────────────────────────────────────────────────────────────────────────────

def detect_chapters(pages: list[dict], pdf_path: str = None) -> list[dict]:
    """
    Detect chapter boundaries using 3 progressive strategies.

    Strategy 1 — Regex (Chapter N, Unit N, numbered lists, roman numerals)
    Strategy 2 — Font-size heading detection (requires pdf_path)
    Strategy 3 — Auto-split (always fires when < 1 chapter per 50 pages found)

    Returns:
        List of chapter dicts: [{'number': 1, 'title': '...', 'page_start': 1, 'page_end': 10}, ...]
    """
    total_pages = pages[-1]['page'] if pages else 1

    # Minimum chapters we expect: at least 1 per 50 pages
    min_expected = max(2, total_pages // 50)

    # ── Strategy 1: Regex ──
    chapters = _detect_by_regex(pages)
    print(f"[Extractor] Strategy 1 (regex): {len(chapters)} chapters found (need >= {min_expected})")

    # ── Strategy 2: Font-size heading ──
    if len(chapters) < min_expected and pdf_path:
        font_chapters = _detect_by_font_size(pdf_path, pages)
        print(f"[Extractor] Strategy 2 (font-size): {len(font_chapters)} chapters found")

        # Accept font chapters only if they're more useful than what we have
        if len(font_chapters) > len(chapters):
            chapters = font_chapters

        # Deduplicate if too many (noise)
        if len(chapters) > 60:
            seen_pages = set()
            deduped = []
            for ch in sorted(chapters, key=lambda c: c['page_start']):
                if ch['page_start'] not in seen_pages:
                    seen_pages.add(ch['page_start'])
                    deduped.append(ch)
            chapters = deduped[:50]

    # ── Strategy 3: Auto-split — ALWAYS fires when not enough chapters ──
    if len(chapters) < min_expected:
        if total_pages <= 50:
            chunk = 10
        elif total_pages <= 150:
            chunk = 20
        elif total_pages <= 300:
            chunk = 30
        elif total_pages <= 600:
            chunk = 40
        else:
            chunk = 60

        chapters = _detect_by_split(total_pages, pages_per_chunk=chunk)
        print(f"[Extractor] Strategy 3 (auto-split {chunk}pp): {len(chapters)} chapters for {total_pages}-page PDF")

    # ── Sort + re-number ──
    chapters.sort(key=lambda c: c['page_start'])
    for i, ch in enumerate(chapters):
        ch['number'] = i + 1

    # ── Assign page_end properly ──
    for i, chapter in enumerate(chapters):
        if i + 1 < len(chapters):
            chapter['page_end'] = chapters[i + 1]['page_start'] - 1
        else:
            chapter['page_end'] = total_pages
        if chapter['page_end'] < chapter['page_start']:
            chapter['page_end'] = chapter['page_start']

    print(f"[Extractor] Final: {len(chapters)} chapters for {total_pages}-page PDF")
    return chapters


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_chapter_text(pages: list[dict], page_start: int, page_end: int) -> str:
    """Extract combined text for a specific page range."""
    texts = [
        p['text'] for p in pages
        if page_start <= p['page'] <= page_end and p['text']
    ]
    return '\n\n'.join(texts)


def get_total_pages(pdf_path: str) -> int:
    """Return the total number of pages in a PDF."""
    try:
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0
