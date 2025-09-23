from django.db import models

from .parsed_text import ParsedDocument


class SimulationSession(models.Model):
    """A user-run simulation for a given document with chosen scenario and parameters."""

    SCENARIO_CHOICES = (
        ("normal", "Normal"),
        ("missed_payment", "Missed Payment"),
        ("early_termination", "Early Termination"),
    )

    document = models.ForeignKey(ParsedDocument, on_delete=models.CASCADE, related_name="simulations")
    title = models.CharField(max_length=255, blank=True, default="")
    scenario = models.CharField(max_length=32, choices=SCENARIO_CHOICES, default="normal")
    parameters = models.JSONField(default=dict, blank=True)
    jurisdiction = models.CharField(max_length=128, blank=True, default="")
    jurisdiction_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - simple
        return f"SimulationSession(doc={self.document_id}, scenario={self.scenario})"


class SimulationTimelineNode(models.Model):
    """Serializable timeline node for the interactive timeline view."""

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="timeline")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=512, blank=True, default="")
    detailed_description = models.TextField(blank=True, default="")
    risks = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:  # pragma: no cover - simple
        return f"TimelineNode(session={self.session_id}, order={self.order}, title={self.title[:24]})"


class SimulationPenaltyForecast(models.Model):
    """Tabular forecast of base, fees, penalties and totals per period."""

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="penalty_forecast")
    label = models.CharField(max_length=64)  # e.g., "Month 1", "Month 6"
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    fees_amount = models.DecimalField(max_digits=12, decimal_places=2)
    penalties_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:  # pragma: no cover
        return f"PenaltyForecast(session={self.session_id}, label={self.label})"


class SimulationExitComparison(models.Model):
    """Exit/termination scenario comparison entries."""

    RISK_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="exit_comparisons")
    label = models.CharField(max_length=128)  # e.g., "Exit at 6 months"
    penalty_text = models.CharField(max_length=64, blank=True, default="")  # e.g., "₹25,000"
    risk_level = models.CharField(max_length=16, choices=RISK_CHOICES, default="low")
    benefits_lost = models.CharField(max_length=128, blank=True, default="")

    def __str__(self) -> str:  # pragma: no cover
        return f"ExitComparison(session={self.session_id}, label={self.label})"


class SimulationNarrativeOutcome(models.Model):
    """Narrative outcomes with key points and financial impact lists."""

    SEVERITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="narratives")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, default="")
    narrative = models.TextField()
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="low")
    key_points = models.JSONField(default=list, blank=True)
    financial_impact = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"NarrativeOutcome(session={self.session_id}, title={self.title[:24]})"


class SimulationLongTermPoint(models.Model):
    """Data points for long-term forecast chart."""

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="long_term")
    index = models.PositiveIntegerField(default=0)  # month index or sequence
    label = models.CharField(max_length=64, blank=True, default="")  # optional display label
    value = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, default="")  # optional description

    class Meta:
        ordering = ["index", "id"]

    def __str__(self) -> str:  # pragma: no cover
        return f"LongTermPoint(session={self.session_id}, idx={self.index}, value={self.value})"


class SimulationRiskAlert(models.Model):
    """Risk alerts surfaced during the simulation."""

    LEVEL_CHOICES = (
        ("info", "Info"),
        ("warning", "Warning"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="risk_alerts")
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default="info")
    message = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"RiskAlert(session={self.session_id}, level={self.level})"


class SimulationSessionTranslation(models.Model):
    """Stores translated versions of simulation session data for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    session = models.ForeignKey(SimulationSession, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_title = models.CharField(max_length=255, blank=True, default="")
    translated_jurisdiction = models.CharField(max_length=128, blank=True, default="")
    translated_jurisdiction_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['session', 'language']

    def __str__(self) -> str:
        return f"SimulationSessionTranslation(session={self.session_id}, lang={self.language})"


class SimulationTimelineNodeTranslation(models.Model):
    """Stores translated versions of timeline nodes for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    node = models.ForeignKey(SimulationTimelineNode, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_title = models.CharField(max_length=255)
    translated_description = models.CharField(max_length=512, blank=True, default="")
    translated_detailed_description = models.TextField(blank=True, default="")
    translated_risks = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['node', 'language']

    def __str__(self) -> str:
        return f"TimelineNodeTranslation(node={self.node_id}, lang={self.language})"


class SimulationPenaltyForecastTranslation(models.Model):
    """Stores translated versions of penalty forecast labels for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    forecast = models.ForeignKey(SimulationPenaltyForecast, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_label = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['forecast', 'language']

    def __str__(self) -> str:
        return f"PenaltyForecastTranslation(forecast={self.forecast_id}, lang={self.language})"


class SimulationExitComparisonTranslation(models.Model):
    """Stores translated versions of exit comparison data for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    comparison = models.ForeignKey(SimulationExitComparison, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_label = models.CharField(max_length=128)
    translated_penalty_text = models.CharField(max_length=64, blank=True, default="")
    translated_benefits_lost = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['comparison', 'language']

    def __str__(self) -> str:
        return f"ExitComparisonTranslation(comparison={self.comparison_id}, lang={self.language})"


class SimulationNarrativeOutcomeTranslation(models.Model):
    """Stores translated versions of narrative outcomes for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    outcome = models.ForeignKey(SimulationNarrativeOutcome, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_title = models.CharField(max_length=255)
    translated_subtitle = models.CharField(max_length=255, blank=True, default="")
    translated_narrative = models.TextField()
    translated_key_points = models.JSONField(default=list, blank=True)
    translated_financial_impact = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['outcome', 'language']

    def __str__(self) -> str:
        return f"NarrativeOutcomeTranslation(outcome={self.outcome_id}, lang={self.language})"


class SimulationLongTermPointTranslation(models.Model):
    """Stores translated versions of long-term forecast points for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    point = models.ForeignKey(SimulationLongTermPoint, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_label = models.CharField(max_length=64, blank=True, default="")
    translated_description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['point', 'language']

    def __str__(self) -> str:
        return f"LongTermPointTranslation(point={self.point_id}, lang={self.language})"


class SimulationRiskAlertTranslation(models.Model):
    """Stores translated versions of risk alerts for different languages."""

    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
        ('ta', 'Tamil'),
        ('te', 'Telugu'),
    )

    alert = models.ForeignKey(SimulationRiskAlert, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES)
    translated_message = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['alert', 'language']

    def __str__(self) -> str:
        return f"RiskAlertTranslation(alert={self.alert_id}, lang={self.language})"

