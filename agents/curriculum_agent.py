"""
Agent 1: Curriculum Analyzer
Analyzes chapter text and extracts key concepts with difficulty levels.
"""
import json
from .llm_client import call_ollama, extract_json

SYSTEM_PROMPT = """You are an expert curriculum designer and educational content analyst.
Your job is to analyze textbook chapter content and extract key learning concepts.
Always respond in valid JSON format only. No markdown, no explanation outside JSON.
Do not include any reasoning, thinking, or commentary — output the JSON array and nothing else."""


def _build_prompt(chapter_title: str, truncated_text: str, max_concepts: int) -> str:
    return f"""Analyze this textbook chapter and extract the actual distinct learning concepts
it covers. Base the concepts strictly on what appears in the text below — do NOT invent a
generic "Introduction / Key Principles / Applications" structure. Name each concept after the
real sub-topic it covers (e.g. "Inertia", "Newton's Second Law", "Momentum Conservation"), not
after a generic learning-stage label.

Chapter: {chapter_title}

Chapter Content:
{truncated_text}

Extract between 3 and {max_concepts} concepts — however many distinct sub-topics genuinely
appear in this content. Do not pad the list with filler concepts if the content only supports
fewer than {max_concepts}.

Return a JSON array of concepts. Each concept must have:
- "title": the specific concept name as it would appear in the textbook (max 10 words)
- "description": educational explanation suitable for students (2-3 sentences)
- "difficulty": one of "beginner", "intermediate", or "advanced"
- "order": integer starting from 1, matching the order concepts appear in the text

Example format:
[
  {{
    "title": "Newton's First Law of Motion",
    "description": "An object at rest stays at rest, and an object in motion stays in motion, unless acted upon by an external force. This property of matter is called inertia.",
    "difficulty": "intermediate",
    "order": 1
  }}
]

Return ONLY the JSON array, nothing else."""


def analyze_chapter(chapter_title: str, chapter_text: str, max_concepts: int = 8) -> list[dict]:
    """
    Extract key concepts from a chapter.

    Returns:
        List of concept dicts:
        [{'title': '...', 'description': '...', 'difficulty': 'beginner|intermediate|advanced', 'order': 1}, ...]
    """
    # Truncate text to avoid token limits
    truncated_text = chapter_text[:3000] if len(chapter_text) > 3000 else chapter_text
    prompt = _build_prompt(chapter_title, truncated_text, max_concepts)

    last_error = None
    for attempt in range(2):  # try once, retry once on failure
        try:
            response = call_ollama(prompt, system=SYSTEM_PROMPT, temperature=0.3)
            concepts = extract_json(response)

            if concepts is None:
                last_error = f"could not parse JSON from response (first 200 chars: {response[:200]!r})"
                print(f"[CurriculumAgent] Attempt {attempt+1} failed: {last_error}")
                continue

            if isinstance(concepts, list) and len(concepts) >= 1:
                valid = []
                for i, c in enumerate(concepts[:max_concepts]):
                    if isinstance(c, dict) and 'title' in c:
                        valid.append({
                            'title': str(c.get('title', f'Concept {i+1}'))[:200],
                            'description': str(c.get('description', ''))[:1000],
                            'difficulty': c.get('difficulty', 'intermediate')
                                          if c.get('difficulty') in ('beginner', 'intermediate', 'advanced')
                                          else 'intermediate',
                            'order': i + 1,
                        })
                if valid:
                    return valid

            last_error = f"parsed JSON was not a usable concept list: {concepts!r}"
            print(f"[CurriculumAgent] Attempt {attempt+1} failed: {last_error}")

        except Exception as e:
            last_error = str(e)
            print(f"[CurriculumAgent] Attempt {attempt+1} error: {e}")

    print(f"[CurriculumAgent] All attempts failed for chapter '{chapter_title}', "
          f"using generic fallback. Last error: {last_error}")
    return _fallback_concepts(chapter_title)


def _fallback_concepts(chapter_title: str) -> list[dict]:
    """Fallback concepts when LLM fails."""
    return [
        {
            'title': f'Introduction to {chapter_title}',
            'description': f'The foundational concepts of {chapter_title}.',
            'difficulty': 'beginner',
            'order': 1,
        },
        {
            'title': f'Key Principles of {chapter_title}',
            'description': f'The main principles and rules governing {chapter_title}.',
            'difficulty': 'intermediate',
            'order': 2,
        },
        {
            'title': f'Applications of {chapter_title}',
            'description': f'Real-world applications and examples of {chapter_title}.',
            'difficulty': 'advanced',
            'order': 3,
        },
    ]
