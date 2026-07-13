"""
Agent 2: Storyboard Generator
Converts a concept + RAG context into a dynamically-sized comic storyboard JSON.
Panel count is decided by the LLM based on how much the concept actually needs
(within a min/max range), not fixed to a single number.
"""
from .llm_client import call_ollama, extract_json

SYSTEM_PROMPT = """You are a creative educational storyboard writer.
You create comic book storyboards that explain science and education concepts clearly and engagingly.
Your panels tell a story that teaches through visual scenes with dialogue.
Always respond in valid JSON format only. Do not include any reasoning, thinking, or
commentary — output the JSON array and nothing else."""


def _build_prompt(concept_title, concept_description, context_text, level_note, style_note,
                   min_panels, max_panels):
    return f"""Create an educational comic storyboard for this concept:

Concept: {concept_title}
Description: {concept_description}
Student Level: {level_note}
Art Style: {style_note}

Textbook Context:
{context_text[:2000]}

Decide how many panels this concept genuinely needs to be taught clearly — use as few as
{min_panels} if the concept is simple, or as many as {max_panels} if it has several distinct
steps or sub-ideas that each deserve their own panel. Do not pad with filler panels just to
hit a number, and do not compress multiple distinct ideas into one panel just to stay short.

Design a storyboard that:
1. Starts with a relatable real-world situation that creates a question specific to THIS concept
2. Visually explains the concept step by step, grounded in the textbook context above
3. Shows the "aha!" moment when the student understands
4. Ends with a memorable summary or key takeaway specific to THIS concept (not a generic one)

Every "scene" must be specific to {concept_title} — do not reuse generic classroom/lightbulb
imagery that could apply to any topic.

CRITICAL — concreteness rule: {concept_title} may be an abstract idea (energy, potential,
field, force) that has nothing literal to draw. Do NOT describe it as glowing shapes, swirling
light, geometric patterns, or abstract visual metaphors — a diffusion model asked to draw
"energy radiating outward" with no concrete subject will produce decorative abstract pattern
art, not an educational illustration. Instead, every single scene must contain a literal,
concrete, physically drawable subject: EITHER (a) a specific person (teacher or student) doing
a specific physical action — pointing at a diagram, holding an object,
reacting with an expression — OR (b) a physical object (two balloons for charges, a battery, etc).
Every "characters" field must name an actual person, never be left empty or vague.

CRITICAL — NO TEXT IN IMAGES RULE: NEVER ask the image model to draw text, letters, numbers, equations, or formulas (e.g. do not say "writing E=mc2 on a blackboard" or "a sign saying Voltage"). Image models cannot spell and will only generate illegible gibberish. All text and formulas will be added later as comic overlays (speech bubbles and boxes). The "scene" description must ONLY describe visual physical objects and people.

Return a JSON array of panels ({min_panels}-{max_panels} of them). Each panel must have:
- "panel": panel number, starting from 1
- "title": short panel title in CAPS (e.g., "THE MYSTERY OF THE BUS")
- "scene": detailed visual description for the AI image generator (3-4 sentences describing exactly what to draw, specific to this concept)
- "setting": location/background
- "characters": who is in the scene
- "dialogue": what a character says (1-2 sentences, or empty string if caption only)
- "caption": narrator text at bottom (1 sentence explaining the concept, or empty string)
- "concept_label": key term highlighted in this panel (or empty string)

Example panel:
{{
  "panel": 1,
  "title": "THE MYSTERY OF THE BUS",
  "scene": "A teenage student with black hair and a red hoodie stands inside a stationary school bus, holding onto a pole. Other students are seated around him. The bus is stopped at a bus stop on a sunny day.",
  "setting": "inside a stationary yellow school bus at a bus stop",
  "characters": "teenage boy with black hair and red hoodie, seated students",
  "dialogue": "Why do I fall backward when the bus suddenly moves forward?",
  "caption": "",
  "concept_label": ""
}}

Return ONLY the JSON array."""


def generate_storyboard(
    concept_title: str,
    concept_description: str,
    context_text: str,
    level: str = 'intermediate',
    art_style: str = 'comic',
    min_panels: int = 4,
    max_panels: int = 8,
) -> list[dict]:
    """
    Generate a comic storyboard for a concept. Panel count is dynamic
    (between min_panels and max_panels) based on how much the concept needs.

    Returns:
        List of panel dicts:
        [{'panel': 1, 'scene': '...', 'setting': '...', 'characters': '...', 'dialogue': '...', 'caption': '...', 'concept_label': '...'}, ...]
    """
    level_instructions = {
        'beginner': 'Use simple language and fun analogies. Focus on basic understanding. Avoid equations.',
        'intermediate': 'Balance concepts with real examples. Include key terms. Use relatable scenarios.',
        'revision': 'Include key formulas and important points. Focus on exam-relevant details. Be concise and precise.',
    }
    style_instructions = {
        'comic': 'Colorful American comic book style with expressive characters.',
        'manga': 'Black and white manga style with anime characters.',
        'cartoon': 'Friendly cartoon style suitable for younger students.',
        'realistic': 'Detailed educational illustration style, realistic scenes.',
    }

    level_note = level_instructions.get(level, level_instructions['intermediate'])
    style_note = style_instructions.get(art_style, style_instructions['comic'])
    prompt = _build_prompt(concept_title, concept_description, context_text,
                            f"{level.upper()} - {level_note}", style_note,
                            min_panels, max_panels)

    last_error = None
    for attempt in range(2):  # try once, retry once on failure
        try:
            response = call_ollama(prompt, system=SYSTEM_PROMPT, temperature=0.6, max_tokens=3500)
            panels = extract_json(response)

            if panels is None:
                last_error = f"could not parse JSON (first 200 chars: {response[:200]!r})"
                print(f"[StoryboardAgent] Attempt {attempt+1} failed: {last_error}")
                continue

            if isinstance(panels, list) and len(panels) >= 2:
                validated = []
                for i, panel in enumerate(panels[:max_panels]):
                    if isinstance(panel, dict):
                        # Validate key_points: must be a list of strings
                        raw_kp = panel.get('key_points', [])
                        if isinstance(raw_kp, list):
                            key_points = [str(kp)[:120] for kp in raw_kp if kp][:6]
                        else:
                            key_points = []

                        validated.append({
                            'panel': i + 1,
                            'title': str(panel.get('title', f'PANEL {i+1}'))[:100],
                            'scene': str(panel.get('scene', ''))[:800],
                            'setting': str(panel.get('setting', ''))[:200],
                            'characters': str(panel.get('characters', ''))[:200],
                            'dialogue': str(panel.get('dialogue', ''))[:300],
                            'caption': str(panel.get('caption', ''))[:300],
                            'concept_label': str(panel.get('concept_label', ''))[:100],
                            'formula': str(panel.get('formula', ''))[:200],
                            'key_points': key_points,
                        })

                # If most panels lack a concrete character, the model likely
                # drifted into abstract concept-visualization (a known failure
                # mode on abstract physics topics with small models). Retry
                # once rather than silently shipping abstract-art panels.
                empty_characters = sum(1 for p in validated if len(p['characters'].strip()) < 4)
                if validated and empty_characters > len(validated) / 2 and attempt == 0:
                    last_error = (
                        f"{empty_characters}/{len(validated)} panels had no concrete "
                        f"character described — likely to render as abstract art, retrying"
                    )
                    print(f"[StoryboardAgent] Attempt {attempt+1}: {last_error}")
                    continue

                if len(validated) >= 2:
                    return validated

            last_error = f"parsed JSON was not a usable panel list: {panels!r}"
            print(f"[StoryboardAgent] Attempt {attempt+1} failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            print(f"[StoryboardAgent] Attempt {attempt+1} error: {e}")

    print(f"[StoryboardAgent] All attempts failed for '{concept_title}', "
          f"using generic fallback. Last error: {last_error}")
    return _fallback_storyboard(concept_title, concept_description, min_panels)


def _fallback_storyboard(concept_title: str, concept_description: str, num_panels: int) -> list[dict]:
    """
    Fallback storyboard when the LLM genuinely can't be reached at all
    (e.g. Ollama is down). This is a last resort, not the normal path —
    if you're seeing this content regularly, check the Ollama connection
    and server logs for the "[StoryboardAgent] ... error" lines above.
    """
    base = [
        {
            'panel': 1,
            'title': 'THE QUESTION',
            'scene': f'A curious student sitting at a desk, raising their hand in class, with a thought bubble showing a question mark. The teacher stands at the blackboard.',
            'setting': 'modern classroom',
            'characters': 'curious student, teacher',
            'dialogue': f'Can you explain {concept_title}?',
            'caption': '',
            'concept_label': concept_title,
        },
        {
            'panel': 2,
            'title': 'THE EXPLANATION',
            'scene': f'A teacher points to a detailed diagram on the blackboard explaining {concept_title}. Students look engaged and attentive.',
            'setting': 'classroom with blackboard',
            'characters': 'teacher pointing at blackboard, attentive students',
            'dialogue': '',
            'caption': concept_description[:200] if concept_description else f'This is how {concept_title} works.',
            'concept_label': '',
        },
        {
            'panel': 3,
            'title': 'THE REAL WORLD',
            'scene': f'Students are shown a real-world example of {concept_title} in action, with clear visual indicators and arrows showing the key principles.',
            'setting': 'outdoor real-world location',
            'characters': 'students observing, environment showing concept',
            'dialogue': '',
            'caption': f'We can see {concept_title} in everyday life!',
            'concept_label': '',
        },
        {
            'panel': 4,
            'title': 'KEY TAKEAWAY',
            'scene': f'A bright lightbulb glows above a smiling student who has understood {concept_title}. The key formula or definition is shown on a banner.',
            'setting': 'bright classroom',
            'characters': 'happy student with lightbulb moment',
            'dialogue': 'Now I understand!',
            'caption': f'Remember: {concept_title} is a fundamental principle!',
            'concept_label': concept_title,
        },
    ]
    if num_panels <= len(base):
        return base[:max(2, num_panels)]
    # Pad by repeating a generic "deeper look" panel if a longer fallback was requested
    extra = base[2]
    while len(base) < num_panels:
        base.insert(-1, dict(extra, panel=len(base)))
    for i, p in enumerate(base):
        p['panel'] = i + 1
    return base
