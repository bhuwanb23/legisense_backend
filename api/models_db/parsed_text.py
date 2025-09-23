from django.db import models


class ParsedDocument(models.Model):
    """Stores the parsed output of an uploaded PDF document.

    This model is the canonical definition and is imported in api.models.
    """

    file_name = models.CharField(max_length=255)
    uploaded_file = models.FileField(upload_to='uploads/pdfs/', blank=True, null=True)
    num_pages = models.PositiveIntegerField(default=0)
    # JSON structure from pdf_document_parser.extract_pdf_text
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover - simple model string
        return f"ParsedDocument({self.file_name}, pages={self.num_pages})"

class DocumentAnalysis(models.Model):
    """Stores AI-generated analysis JSON and related metadata for a document."""

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    )

    document = models.OneToOneField(ParsedDocument, on_delete=models.CASCADE, related_name="analysis")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    model = models.CharField(max_length=128, blank=True, default="")
    prompt_version = models.CharField(max_length=32, blank=True, default="v1")
    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)
    output_json = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - simple model string
        return f"DocumentAnalysis(doc={self.document_id}, status={self.status})"


class DocumentTranslation(models.Model):
    """Stores translated versions of document content for different languages."""
    
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )
    
    document = models.ForeignKey(ParsedDocument, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    # Store translated pages as JSON
    translated_pages = models.JSONField()
    # Store translated full text
    translated_full_text = models.TextField(blank=True, default="")
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['document', 'language']
    
    def __str__(self) -> str:  # pragma: no cover - simple model string
        return f"DocumentTranslation(doc={self.document_id}, lang={self.language})"


class DocumentAnalysisTranslation(models.Model):
    """Stores translated versions of document analysis for different languages."""
    
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )
    
    analysis = models.ForeignKey(DocumentAnalysis, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    # Store translated analysis JSON
    translated_analysis_json = models.JSONField()
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['analysis', 'language']
    
    def __str__(self) -> str:  # pragma: no cover - simple model string
        return f"DocumentAnalysisTranslation(analysis={self.analysis_id}, lang={self.language})"