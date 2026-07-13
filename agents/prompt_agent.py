"""
Agent 3: Prompt Generator
Converts storyboard panel descriptions into Animagine XL-optimized prompts.

KEY DESIGN PRINCIPLE:
  The SD model generates a BACKGROUND ILLUSTRATION only.
  ALL text, formulas, key-points, captions are rendered by Pillow.
  So prompts must NEVER ask for text, chalkboard writing, labels, or diagrams with text.
"""

# Animagine XL quality prefix
QUALITY_PREFIX = "masterpiece, best quality, very aesthetic, absurdres"

# Physics/science topics (energy, field, potential, force) are abstract nouns
# with nothing to literally draw. Without this, the model fills the empty
# space with decorative pattern-work — swirls, kaleidoscope tiling, fractal
# collage — because it has no concrete subject to anchor on.
NEGATIVE_BASE = (
    "low quality, worst quality, blurry, watermark, "
    "extra fingers, bad anatomy, cropped, nsfw, ugly, deformed, "
    "bad proportions, mutated, disfigured, "
    "text, letters, words, writing, labels, equations, formula, "
    "chalkboard text, speech bubble text, caption text, "
    "abstract art, abstract pattern, kaleidoscope, fractal, psychedelic, "
    "geometric abstraction, mosaic, tiled pattern, symmetrical pattern, "
    "op art, no subject, no characters, empty scene, pattern background only"
)

ART_STYLE_TOKENS = {
    'comic': 'educational comic illustration, colorful comic book style, clean line art, vibrant colors',
    'manga': 'manga style illustration, black and white, screen tones, anime style',
    'cartoon': 'cartoon illustration, bright and cheerful, friendly character design',
    'realistic': 'detailed educational illustration, realistic style, textbook illustration',
}

SUBJECT_TOKENS = {
    'comic': 'expressive faces, dynamic poses',
    'manga': 'expressive manga faces, dynamic action lines',
    'cartoon': 'big eyes, round faces, simple shapes',
    'realistic': 'accurate anatomy, detailed environment',
}


def build_prompt(panel: dict, art_style: str = 'comic') -> dict:
    """
    Build an Animagine XL background-only prompt from a storyboard panel.

    The prompt describes ONLY the visual scene/background — all educational
    text content (key points, formulas, captions) is overlaid by Pillow.

    Token order: concrete subject → setting → style → mood
    """
    style_tokens = ART_STYLE_TOKENS.get(art_style, ART_STYLE_TOKENS['comic'])
    subject_tokens = SUBJECT_TOKENS.get(art_style, SUBJECT_TOKENS['comic'])

    scene = panel.get('scene', '').strip()
    setting = panel.get('setting', '').strip()
    characters = panel.get('characters', '').strip()

    # If the storyboard agent left characters thin/empty, anchor with a
    # default human subject so there's always something concrete to draw.
    if not characters:
        characters = "a student and teacher in an educational setting"

    parts = [QUALITY_PREFIX]

    # Concrete subject FIRST — this is the actual anchor for SD.
    if characters:
        parts.append(characters)
    if scene:
        parts.append(scene)
    if setting:
        parts.append(f"setting: {setting}")

    # Style/mood tokens after the subject.
    parts.append(style_tokens)
    parts.append(subject_tokens)

    parts.extend([
        'one clear focal scene',
        'single coherent illustration',
        'clear composition',
        'suitable for educational content',
        'high detail',
        'no text overlay',
        'no written words in image',
    ])

    positive = ', '.join(p.strip() for p in parts if p.strip())

    # Build negative prompt
    extra_neg = []
    if art_style in ('comic', 'manga', 'cartoon'):
        extra_neg.append('photorealistic, 3d render, photography')

    negative = NEGATIVE_BASE
    if extra_neg:
        negative = negative + ', ' + ', '.join(extra_neg)

    return {'positive': positive, 'negative': negative}


def build_all_prompts(storyboard: list[dict], art_style: str = 'comic') -> list[dict]:
    """
    Build background illustration prompts for all panels in a storyboard.

    Returns:
        List of dicts: [{'panel': 1, 'positive': '...', 'negative': '...'}, ...]
    """
    results = []
    for panel in storyboard:
        prompts = build_prompt(panel, art_style)
        results.append({
            'panel': panel.get('panel', len(results) + 1),
            'positive': prompts['positive'],
            'negative': prompts['negative'],
        })
    return results
