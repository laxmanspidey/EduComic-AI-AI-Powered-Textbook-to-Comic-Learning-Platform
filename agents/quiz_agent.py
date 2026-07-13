"""
Agent 4: Quiz Generator
Generates multiple-choice quiz questions for a concept.
"""
from .llm_client import call_ollama, extract_json

SYSTEM_PROMPT = """You are an expert educational assessment designer.
You create clear, fair, and educationally valuable multiple-choice questions.
Always respond in valid JSON format only."""


def generate_quiz(concept_title: str, concept_description: str,
                  context_text: str = '', level: str = 'intermediate',
                  num_questions: int = 3) -> list[dict]:
    """
    Generate quiz questions for a concept.

    Returns:
        List of quiz dicts:
        [{'question': '...', 'options': ['A', 'B', 'C', 'D'], 'correct_index': 0, 'explanation': '...'}, ...]
    """
    level_note = {
        'beginner': 'Simple recall questions, no equations.',
        'intermediate': 'Application questions, reasoning required.',
        'revision': 'Mixed recall and application, exam-style.',
    }.get(level, 'Application questions.')

    prompt = f"""Create {num_questions} multiple-choice quiz questions about this concept:

Concept: {concept_title}
Description: {concept_description}
Level: {level.upper()} - {level_note}

Context:
{context_text[:1500] if context_text else 'Use your knowledge of this topic.'}

Requirements:
- Each question has exactly 4 options (A, B, C, D)
- Only one option is correct
- Options should be plausible (not obviously wrong)
- Include a brief explanation of why the correct answer is right
- Questions should test understanding, not just memorization

Return a JSON array:
[
  {{
    "question": "Question text here?",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "correct_index": 0,
    "explanation": "Option A is correct because..."
  }}
]

Return ONLY the JSON array."""

    try:
        response = call_ollama(prompt, system=SYSTEM_PROMPT, temperature=0.4, max_tokens=4000)
        questions = extract_json(response)

        if isinstance(questions, list):
            validated = []
            for q in questions[:num_questions]:
                if isinstance(q, dict) and 'question' in q and 'options' in q:
                    options = q.get('options', [])
                    if len(options) == 4:
                        correct_idx = q.get('correct_index', 0)
                        if not isinstance(correct_idx, int) or not (0 <= correct_idx <= 3):
                            correct_idx = 0
                        validated.append({
                            'question': str(q['question'])[:500],
                            'options': [str(o)[:200] for o in options],
                            'correct_index': correct_idx,
                            'explanation': str(q.get('explanation', ''))[:500],
                        })
            if validated:
                return validated
    except Exception as e:
        print(f"[QuizAgent] Error: {e}")

    # Fallback
    return _fallback_quiz(concept_title)


def _fallback_quiz(concept_title: str) -> list[dict]:
    return [
        {
            'question': f'What is the main idea of {concept_title}?',
            'options': [
                f'{concept_title} is a key principle in this subject',
                'It is not important',
                'It only applies in theory',
                'None of the above',
            ],
            'correct_index': 0,
            'explanation': f'{concept_title} is indeed a key principle that has wide applications.',
        }
    ]
