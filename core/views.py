"""
All Django views for the AI Comic Textbook application.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django_q.tasks import async_task

from .models import (
    Textbook, Chapter, Concept, ComicStrip, ComicPanel, Quiz, StudentProgress
)
from .forms import TextbookUploadForm, RegisterForm


# ─── Authentication ───────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Let's start learning.")
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'core/register.html', {'form': form})


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    textbooks = Textbook.objects.filter(user=request.user)
    recent_comics = ComicStrip.objects.filter(
        user=request.user, status='ready'
    ).select_related('concept__chapter__textbook')[:6]

    # Calculate overall progress
    total_concepts = Concept.objects.filter(
        chapter__textbook__user=request.user
    ).count()
    viewed_concepts = StudentProgress.objects.filter(
        user=request.user, viewed=True
    ).count()

    context = {
        'textbooks': textbooks,
        'recent_comics': recent_comics,
        'total_concepts': total_concepts,
        'viewed_concepts': viewed_concepts,
    }
    return render(request, 'core/dashboard.html', context)


# ─── Textbook Upload & Detail ─────────────────────────────────────────────────

@login_required
def textbook_upload(request):
    if request.method == 'POST':
        form = TextbookUploadForm(request.POST, request.FILES)
        if form.is_valid():
            textbook = form.save(commit=False)
            textbook.user = request.user
            textbook.save()

            # Queue background processing task
            async_task(
                'tasks.comic_tasks.process_textbook',
                str(textbook.id),
                task_name=f'process_textbook_{textbook.id}',
            )
            messages.success(request, f'"{textbook.title}" uploaded! Processing chapters...')
            return redirect('textbook_detail', pk=textbook.pk)
        else:
            messages.error(request, 'Upload failed. Please check the form.')
    else:
        form = TextbookUploadForm()
    return render(request, 'core/textbook_upload.html', {'form': form})


@login_required
def textbook_detail(request, pk):
    textbook = get_object_or_404(Textbook, pk=pk, user=request.user)
    chapters = textbook.chapters.prefetch_related('concepts').all()
    context = {
        'textbook': textbook,
        'chapters': chapters,
    }
    return render(request, 'core/textbook_detail.html', context)


@login_required
@require_POST
def reprocess_textbook(request, pk):
    """Re-run the chapter detection + RAG pipeline on an existing textbook."""
    textbook = get_object_or_404(Textbook, pk=pk, user=request.user)

    # Delete old chapters, concepts, and ChromaDB collection
    from rag.embedder import delete_collection
    textbook.chapters.all().delete()
    try:
        delete_collection(str(textbook.id))
    except Exception:
        pass

    textbook.status = 'processing'
    textbook.error_message = ''
    textbook.save(update_fields=['status', 'error_message'])

    async_task(
        'tasks.comic_tasks.process_textbook',
        str(textbook.id),
        task_name=f'reprocess_textbook_{textbook.id}',
    )
    messages.success(request, 'Re-processing started with improved chapter detection!')
    return redirect('textbook_detail', pk=textbook.pk)


@login_required
def textbook_status_api(request, pk):
    """AJAX endpoint for polling textbook processing status."""
    textbook = get_object_or_404(Textbook, pk=pk, user=request.user)
    return JsonResponse({
        'status': textbook.status,
        'chapter_count': textbook.chapter_count,
        'concept_count': textbook.concept_count,
        'total_pages': textbook.total_pages,
        'error': textbook.error_message,
    })


# ─── Concept & Comic ─────────────────────────────────────────────────────────

@login_required
def concept_detail(request, pk):
    concept = get_object_or_404(Concept, pk=pk)
    textbook = concept.chapter.textbook

    # Only allow owner
    if textbook.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    # Track progress
    progress, _ = StudentProgress.objects.get_or_create(
        user=request.user, concept=concept
    )
    if not progress.viewed:
        progress.viewed = True
        progress.save(update_fields=['viewed'])

    # Get existing comic strips
    comics = concept.comic_strips.filter(user=request.user)

    # Get quizzes
    quizzes = concept.quizzes.all()

    context = {
        'concept': concept,
        'textbook': textbook,
        'comics': comics,
        'quizzes': quizzes,
        'progress': progress,
    }
    return render(request, 'core/concept_detail.html', context)


@login_required
@require_POST
def generate_comic_view(request, concept_pk):
    """Start comic generation for a concept."""
    concept = get_object_or_404(Concept, pk=concept_pk)
    textbook = concept.chapter.textbook

    if textbook.user != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)

    level = request.POST.get('level', 'intermediate')
    art_style = request.POST.get('art_style', 'comic')

    if level not in ('beginner', 'intermediate', 'revision'):
        level = 'intermediate'
    if art_style not in ('comic', 'manga', 'cartoon', 'realistic'):
        art_style = 'comic'

    # Create the comic strip record
    comic_strip = ComicStrip.objects.create(
        concept=concept,
        user=request.user,
        level=level,
        art_style=art_style,
        status='pending',
    )

    # Queue background generation
    async_task(
        'tasks.comic_tasks.generate_comic',
        str(comic_strip.id),
        task_name=f'generate_comic_{comic_strip.id}',
    )

    return JsonResponse({
        'comic_id': str(comic_strip.id),
        'status': 'pending',
        'message': 'Comic generation started! This takes 2-5 minutes.',
    })


@login_required
def comic_view(request, pk):
    """View a generated comic strip."""
    comic = get_object_or_404(ComicStrip, pk=pk, user=request.user)
    panels = comic.panels.all()
    concept = comic.concept
    quizzes = concept.quizzes.all()

    # Adjacent panels for nav
    all_concepts = list(concept.chapter.concepts.values_list('id', flat=True))
    current_idx = list(all_concepts).index(concept.id) if concept.id in all_concepts else 0

    prev_concept = None
    next_concept = None
    if current_idx > 0:
        prev_concept = Concept.objects.get(id=all_concepts[current_idx - 1])
    if current_idx < len(all_concepts) - 1:
        next_concept = Concept.objects.get(id=all_concepts[current_idx + 1])

    context = {
        'comic': comic,
        'panels': panels,
        'concept': concept,
        'quizzes': quizzes,
        'prev_concept': prev_concept,
        'next_concept': next_concept,
        'total_panels': len(panels),
    }
    return render(request, 'core/comic_view.html', context)


@login_required
def comic_status_api(request, pk):
    """AJAX poll for comic generation status."""
    comic = get_object_or_404(ComicStrip, pk=pk, user=request.user)
    panels = list(comic.panels.values('panel_number', 'image'))
    return JsonResponse({
        'status': comic.status,
        'panel_count': comic.panel_count,
        'error': comic.error_message,
        'panels_ready': len(panels),
    })


@login_required
@require_POST
def rerender_comic(request, pk):
    """
    Re-apply the Pillow overlay to all existing panels.
    For panels without key_points (old format), uses the LLM content agent
    to generate real educational facts before composing.
    """
    from comicgen.panel_composer import add_panel_overlay
    from agents.content_agent import enrich_panel
    from django.core.files.base import ContentFile

    comic = get_object_or_404(ComicStrip, pk=pk, user=request.user)
    storyboard = comic.storyboard or []
    concept_title = comic.concept.title
    level = comic.level

    # Build panel_number → storyboard panel lookup
    sb_map = {p.get('panel', i + 1): p for i, p in enumerate(storyboard)}

    panels = comic.panels.all()
    rerendered = 0

    for panel in panels:
        # Get storyboard data for this panel, or build from DB fields
        panel_data = sb_map.get(panel.panel_number, {
            'panel': panel.panel_number,
            'title': f'PANEL {panel.panel_number}',
            'key_points': [],
            'formula': '',
            'caption': panel.caption or '',
            'dialogue': panel.dialogue or '',
            'concept_label': panel.concept_label or '',
            'scene': panel.scene_description or '',
        })

        # Enrich with LLM-generated educational content if key_points are missing
        panel_data = enrich_panel(panel_data, concept_title=concept_title, level=level)

        try:
            panel.image.open()
            raw_bytes = panel.image.read()
            panel.image.close()

            composed_bytes = add_panel_overlay(raw_bytes, panel_data)
            filename = panel.image.name.split('/')[-1]
            panel.image.save(filename, ContentFile(composed_bytes), save=True)

            # Also update the storyboard entry with enriched data
            if panel.panel_number in sb_map:
                sb_map[panel.panel_number] = panel_data

            rerendered += 1
            print(f'[ReRender] Panel {panel.panel_number} done')
        except Exception as e:
            print(f'[ReRender] Panel {panel.panel_number} error: {e}')
            import traceback; traceback.print_exc()

    # Save updated storyboard back to comic
    if storyboard:
        updated_sb = [sb_map.get(i + 1, storyboard[i]) for i in range(len(storyboard))]
        comic.storyboard = updated_sb
        comic.save(update_fields=['storyboard'])

    messages.success(request, f'✅ Re-rendered {rerendered} panels with AI-generated educational content!')
    return redirect('comic_view', pk=comic.pk)





# ─── Quiz ─────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def submit_quiz(request, quiz_pk):
    """Submit a quiz answer."""
    quiz = get_object_or_404(Quiz, pk=quiz_pk)
    concept = quiz.concept

    # Owner check
    if concept.chapter.textbook.user != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)

    selected = request.POST.get('selected_index')
    try:
        selected_idx = int(selected)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid selection'}, status=400)

    is_correct = (selected_idx == quiz.correct_index)

    # Update progress
    progress, _ = StudentProgress.objects.get_or_create(
        user=request.user, concept=concept
    )
    progress.quiz_attempts += 1
    if is_correct:
        progress.quiz_correct += 1
    progress.save(update_fields=['quiz_attempts', 'quiz_correct'])

    return JsonResponse({
        'correct': is_correct,
        'correct_index': quiz.correct_index,
        'explanation': quiz.explanation,
        'score_pct': progress.quiz_score_pct,
    })


# ─── Library ──────────────────────────────────────────────────────────────────

@login_required
def my_library(request):
    """Student's saved comics library."""
    comics = ComicStrip.objects.filter(
        user=request.user, status='ready'
    ).select_related('concept__chapter__textbook').order_by('-created_at')
    return render(request, 'core/library.html', {'comics': comics})


# ─── Progress ─────────────────────────────────────────────────────────────────

@login_required
def my_progress(request):
    """Student progress overview."""
    progress_items = StudentProgress.objects.filter(
        user=request.user
    ).select_related('concept__chapter__textbook')

    textbooks = Textbook.objects.filter(user=request.user, status='ready')
    context = {
        'progress_items': progress_items,
        'textbooks': textbooks,
    }
    return render(request, 'core/progress.html', context)
