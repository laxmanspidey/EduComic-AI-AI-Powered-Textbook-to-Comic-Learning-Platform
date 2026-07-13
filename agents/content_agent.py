"""
Content Agent — LLM-powered educational key_points generator.

Called when:
  1. Storyboard panels have no key_points (old format)
  2. Re-rendering existing panels with improved content

Uses Ollama (qwen3:7b or configured model) to generate accurate,
specific educational facts suitable for display in panel info-boxes.
"""
from .llm_client import call_ollama, extract_json

SYSTEM = (
    "You are an expert educational content writer specializing in textbook comics. "
    "You write concise, accurate, exam-focused facts for students. "
    "Always return valid JSON. No thinking text, no explanations outside JSON."
)


def generate_key_points(
    concept_title: str,
    panel_title: str,
    caption: str = '',
    dialogue: str = '',
    level: str = 'intermediate',
) -> list[str]:
    """
    Use LLM to generate 4 specific, factual key_points for a panel.

    Returns:
        List of 4 concise educational strings (max ~12 words each).
        Falls back to caption-based splits on LLM failure.
    """
    context = '\n'.join(filter(None, [caption, dialogue]))

    prompt = f"""Generate exactly 4 educational key facts for a comic panel.

Concept: {concept_title}
Panel: {panel_title}
Context clue: {context[:300] if context else '(none)'}

Rules:
- Each fact must be a REAL, specific educational truth about "{concept_title}"
- Maximum 12 words per fact
- Cover: definition, why it matters, a formula if applicable, a real example
- NO generic statements like "refer to textbook" or "see derivation"
- Be exam-relevant and precise

Return ONLY a JSON array of exactly 4 strings. Example format:
["Electric potential is constant on conductor surface", "E field is zero inside a conductor", "Charges always reside on outer surface only", "Surface forms an equipotential: V = const"]"""

    try:
        raw = call_ollama(prompt, system=SYSTEM, temperature=0.2, max_tokens=300)
        points = extract_json(raw)
        if isinstance(points, list):
            valid = [str(p).strip() for p in points if p and len(str(p).strip()) > 4]
            if len(valid) >= 2:
                return valid[:4]
    except Exception as e:
        print(f"[ContentAgent] LLM key_points failed for '{panel_title}': {e}")

    # Graceful fallback: split caption into sentences
    import re
    if caption:
        parts = [s.strip().rstrip('.') for s in re.split(r'[.;]', caption) if len(s.strip()) > 8]
        if len(parts) >= 2:
            return parts[:4]

    return [f'{concept_title}: core educational concept', 'Study this topic in your textbook']


def generate_formula(
    concept_title: str,
    panel_title: str,
    caption: str = '',
) -> str:
    """
    Use LLM to extract/generate the key formula for this panel, if any.
    Returns empty string if no formula applies.
    """
    prompt = f"""Does the topic "{concept_title}" — panel "{panel_title}" — have a key formula?
    
Context: {caption[:200] if caption else '(none)'}

If YES, return a JSON object with the formula: {{"formula": "F = ma"}}
If NO, return: {{"formula": ""}}

ONLY return valid JSON. Do not explain."""

    try:
        raw = call_ollama(prompt, system=SYSTEM, temperature=0.1, max_tokens=100)
        data = extract_json(raw)
        if isinstance(data, dict):
            return data.get('formula', '').strip()
    except Exception as e:
        print(f"[ContentAgent] Formula generation failed: {e}")
    return ''


def enrich_panel(panel: dict, concept_title: str, level: str = 'intermediate') -> dict:
    """
    Enrich a panel dict with LLM-generated key_points and formula
    if these are missing (old storyboard format).

    Returns a new panel dict with the fields filled in.
    """
    enriched = dict(panel)

    kp = [p for p in (panel.get('key_points') or []) if str(p).strip()]
    if len(kp) < 2:
        print(f"[ContentAgent] Generating key_points for: {panel.get('title', '?')}")
        enriched['key_points'] = generate_key_points(
            concept_title=concept_title,
            panel_title=panel.get('title', concept_title),
            caption=panel.get('caption', ''),
            dialogue=panel.get('dialogue', ''),
            level=level,
        )

    if not panel.get('formula', '').strip():
        formula = generate_formula(
            concept_title=concept_title,
            panel_title=panel.get('title', concept_title),
            caption=panel.get('caption', ''),
        )
        if formula:
            enriched['formula'] = formula

    return enriched
