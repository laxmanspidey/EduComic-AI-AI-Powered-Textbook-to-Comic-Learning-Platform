from django.db import models
from django.contrib.auth.models import User
import uuid


class Textbook(models.Model):
    """Represents an uploaded PDF textbook."""
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='textbooks')
    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=100, blank=True)
    grade_level = models.CharField(max_length=50, blank=True)
    pdf_file = models.FileField(upload_to='textbooks/')
    thumbnail = models.ImageField(upload_to='textbook_thumbs/', null=True, blank=True)
    total_pages = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def chapter_count(self):
        return self.chapters.count()

    @property
    def concept_count(self):
        return Concept.objects.filter(chapter__textbook=self).count()


class Chapter(models.Model):
    """A chapter within a textbook."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=255)
    number = models.IntegerField(default=1)
    page_start = models.IntegerField(default=0)
    page_end = models.IntegerField(default=0)
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f"Chapter {self.number}: {self.title}"


class Concept(models.Model):
    """A key concept within a chapter."""
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='concepts')
    title = models.CharField(max_length=255)
    description = models.TextField()
    page_references = models.JSONField(default=list)   # list of page numbers
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class ComicStrip(models.Model):
    """A generated comic for a concept."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('error', 'Error'),
    ]

    ART_STYLE_CHOICES = [
        ('comic', 'Comic'),
        ('manga', 'Manga'),
        ('cartoon', 'Cartoon'),
        ('realistic', 'Realistic Illustration'),
    ]

    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('revision', 'Exam Revision'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='comic_strips')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comic_strips')
    title = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='intermediate')
    art_style = models.CharField(max_length=20, choices=ART_STYLE_CHOICES, default='comic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    storyboard = models.JSONField(default=list)   # list of scene dicts
    layout_image = models.ImageField(upload_to='comics/', null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comic: {self.concept.title} ({self.level})"

    @property
    def panel_count(self):
        return self.panels.count()


class ComicPanel(models.Model):
    """A single panel in a comic strip."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comic_strip = models.ForeignKey(ComicStrip, on_delete=models.CASCADE, related_name='panels')
    panel_number = models.IntegerField()
    scene_description = models.TextField()
    dialogue = models.TextField(blank=True)
    caption = models.TextField(blank=True)
    concept_label = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='panels/', null=True, blank=True)
    prompt_used = models.TextField(blank=True)
    comfyui_prompt_id = models.CharField(max_length=100, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['panel_number']

    def __str__(self):
        return f"Panel {self.panel_number} of {self.comic_strip}"


class Quiz(models.Model):
    """A quiz associated with a concept."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='quizzes')
    question = models.TextField()
    options = models.JSONField(default=list)        # list of 4 strings
    correct_index = models.IntegerField(default=0)  # 0-indexed
    explanation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Quiz: {self.question[:60]}..."


class StudentProgress(models.Model):
    """Track student progress per concept."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='progress')
    viewed = models.BooleanField(default=False)
    quiz_attempts = models.IntegerField(default=0)
    quiz_correct = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'concept']

    def __str__(self):
        return f"{self.user.username} - {self.concept.title}"

    @property
    def quiz_score_pct(self):
        if self.quiz_attempts == 0:
            return 0
        return int((self.quiz_correct / self.quiz_attempts) * 100)
