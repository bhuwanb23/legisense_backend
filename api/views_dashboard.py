from django.shortcuts import render
from django.core.paginator import Paginator


def home_dashboard_view(request):
    # Import models locally to avoid circular imports during checks
    from .models import (
        ParsedDocument,
        DocumentAnalysis,
        SimulationSession,
        SimulationRiskAlert,
        SimulationLongTermPoint,
        DocumentTranslation,
        DocumentAnalysisTranslation,
        SimulationExitComparison,
        SimulationNarrativeOutcome,
    )

    per_page = 10

    def paginated(name: str, queryset):
        page_param = f"{name}_page"
        page_number = request.GET.get(page_param, 1)
        paginator = Paginator(queryset, per_page)
        page_obj = paginator.get_page(page_number)
        return {
            "items": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "page_param": page_param,
        }

    context = {
        "docs": paginated("docs", ParsedDocument.objects.all().order_by("-id")),
        "analyses": paginated("analyses", DocumentAnalysis.objects.all().order_by("-id")),
        "sim_sessions": paginated("sim_sessions", SimulationSession.objects.all().order_by("-id")),
        "sim_risks": paginated("sim_risks", SimulationRiskAlert.objects.all().order_by("-id")),
        "sim_long_term": paginated("sim_long_term", SimulationLongTermPoint.objects.all().order_by("-id")),
        "doc_translations": paginated("doc_translations", DocumentTranslation.objects.all().order_by("-id")),
        "analysis_translations": paginated("analysis_translations", DocumentAnalysisTranslation.objects.all().order_by("-id")),
        "sim_exit_comparisons": paginated("sim_exit_comparisons", SimulationExitComparison.objects.all().order_by("-id")),
        "sim_narratives": paginated("sim_narratives", SimulationNarrativeOutcome.objects.all().order_by("-id")),
    }

    return render(request, "index.html", context)


