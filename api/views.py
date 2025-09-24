from pathlib import Path
import tempfile
import json

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import (
    ParsedDocument, DocumentAnalysis, DocumentTranslation, DocumentAnalysisTranslation,
    SimulationSession, SimulationTimelineNode, SimulationPenaltyForecast, SimulationExitComparison,
    SimulationNarrativeOutcome, SimulationLongTermPoint, SimulationRiskAlert,
    SimulationSessionTranslation, SimulationTimelineNodeTranslation, SimulationPenaltyForecastTranslation,
    SimulationExitComparisonTranslation, SimulationNarrativeOutcomeTranslation,
    SimulationLongTermPointTranslation, SimulationRiskAlertTranslation
)
from documents.pdf_document_parser import extract_pdf_text
from ai_models.run_analysis import call_openrouter_for_analysis
from translation.translator import DocumentTranslator
import threading
from ai_models.api.google_gemini_api import GoogleGeminiAPI, GeminiAPIError

# Default system prompt for Gemini chat
_GEMINI_SYSTEM_PROMPT = (
    "You are Legisense AI, a helpful assistant specialized in legal documents, "
    "compliance, and jurisdiction-related inquiries. Provide concise, clear, and "
    "honest answers. When uncertain, say you are unsure and suggest what information "
    "would clarify the issue. Avoid giving legal, medical, or financial advice; "
    "instead provide educational, general information and prompt users to consult a "
    "licensed professional for decisions. Prefer structured, bullet-pointed answers, "
    "and call out jurisdictional differences explicitly when relevant."
)


@csrf_exempt
def parse_pdf_view(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "No file uploaded."}, status=400)

    # Save to a temporary file to pass a filesystem path to the parser
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        data = extract_pdf_text(tmp_path)
    except Exception as exc:  # noqa: BLE001 - bubble parser errors
        return JsonResponse({"error": str(exc)}, status=500)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Fallback: if parser returned no page texts, synthesize from full_text
    try:
        pages = data.get("pages") or []
        if not pages:
            full_text = (data.get("full_text") or "").strip()
            if full_text:
                # Split by form-feed if present; otherwise make a single page
                candidates = [p for p in full_text.split("\f") if p.strip()]
                if not candidates:
                    candidates = [full_text]
                data["pages"] = [
                    {"page_number": i + 1, "text": txt}
                    for i, txt in enumerate(candidates)
                ]
                data["num_pages"] = len(data["pages"])  # keep num_pages consistent
    except Exception:
        # If anything goes wrong in fallback, keep original data as-is
        pass

    # Create DB record and also persist the uploaded file into MEDIA_ROOT
    # Always prefer the original uploaded file name; do not use parser temp path
    doc = ParsedDocument(
        file_name=Path(uploaded_file.name).name,
        num_pages=int(data.get("num_pages") or 0),
        payload=data,
    )
    # Attach uploaded file contents
    uploaded_file.seek(0)
    doc.uploaded_file.save(uploaded_file.name, ContentFile(uploaded_file.read()), save=False)
    doc.save()

    # Include id and stored file URL for client convenience
    response = dict(data)
    response["id"] = doc.id
    response["file_url"] = doc.uploaded_file.url if doc.uploaded_file else None
    response["file_name"] = doc.file_name

    # Run analysis synchronously (Render allows ~30–60s). This ensures
    # the client gets analysis immediately without extra polling.
    analysis_obj = None
    try:
        meta = {"file_name": doc.file_name, "num_pages": doc.num_pages}
        pages = [p.get("text", "") for p in data.get("pages", [])]
        analysis_payload = call_openrouter_for_analysis(pages, meta)
        analysis_obj, _ = DocumentAnalysis.objects.update_or_create(
            document=doc,
            defaults={
                "status": "success" if analysis_payload else "failed",
                "output_json": analysis_payload or {},
                "model": "openrouter",
            },
        )
    except Exception as exc:  # noqa: BLE001
        analysis_obj, _ = DocumentAnalysis.objects.update_or_create(
            document=doc,
            defaults={"status": "failed", "error": str(exc)},
        )

    # Trigger translations for all supported languages (background process)
    if analysis_obj and analysis_obj.status == "success":
        try:
            _translate_document_async(doc.id, data)
            _translate_analysis_async(analysis_obj.id, analysis_obj.output_json)
        except Exception as exc:  # noqa: BLE001
            print(f"Background translation failed for document {doc.id}: {exc}")

    response["analysis_available"] = DocumentAnalysis.objects.filter(document=doc, status="success").exists()
    return JsonResponse(response)


def list_parsed_docs_view(request: HttpRequest):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    qs = ParsedDocument.objects.order_by("-created_at").values("id", "file_name", "num_pages", "created_at")
    return JsonResponse({"results": list(qs)})


def parsed_doc_detail_view(request: HttpRequest, pk: int):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    doc = get_object_or_404(ParsedDocument, pk=pk)
    data = dict(doc.payload)
    data["id"] = doc.id
    data["file_name"] = doc.file_name
    data["num_pages"] = doc.num_pages
    data["file_url"] = doc.uploaded_file.url if doc.uploaded_file else None
    data["analysis_available"] = hasattr(doc, "analysis") and doc.analysis.status == "success"
    return JsonResponse(data)


def parsed_doc_analysis_view(request: HttpRequest, pk: int):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    doc = get_object_or_404(ParsedDocument, pk=pk)
    if not hasattr(doc, "analysis"):
        return JsonResponse({"status": "pending"})
    if doc.analysis.status != "success":
        # Surface current status and error if any, so clients can decide to poll
        return JsonResponse({
            "status": doc.analysis.status,
            "error": getattr(doc.analysis, "error", "")
        })
    return JsonResponse({"id": doc.analysis.id, "status": "success", "analysis": doc.analysis.output_json})


@csrf_exempt
def parsed_doc_analyze_view(request: HttpRequest, pk: int):
    """(Re)run analysis for a given document and persist result."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    doc = get_object_or_404(ParsedDocument, pk=pk)
    payload = doc.payload or {}
    pages = [p.get("text", "") for p in payload.get("pages", [])]
    meta = {"file_name": doc.file_name, "num_pages": doc.num_pages}
    try:
        analysis_payload = call_openrouter_for_analysis(pages, meta)
        obj, _ = DocumentAnalysis.objects.update_or_create(
            document=doc,
            defaults={
                "status": "success" if analysis_payload else "failed",
                "output_json": analysis_payload or {},
                "model": "openrouter",
                "error": "" if analysis_payload else "empty response",
            },
        )
        return JsonResponse({"status": obj.status, "analysis": obj.output_json})
    except Exception as exc:  # noqa: BLE001
        obj, _ = DocumentAnalysis.objects.update_or_create(
            document=doc,
            defaults={"status": "failed", "error": str(exc)},
        )
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
@transaction.atomic
def parsed_doc_simulate_view(request: HttpRequest, pk: int):
    """Generate simulation JSON via OpenRouter and persist records for a document."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    doc = get_object_or_404(ParsedDocument, pk=pk)

    # Check if document already has simulations
    from .models import SimulationSession
    existing_simulations = SimulationSession.objects.filter(document=doc).order_by('-created_at')
    
    if existing_simulations.exists():
        # Return the most recent simulation session ID
        latest_simulation = existing_simulations.first()
        print(f"🔍 Found existing simulation for document {pk}: session_id={latest_simulation.id}")
        return JsonResponse({
            "status": "ok", 
            "session_id": latest_simulation.id,
            "cached": True,
            "message": "Using existing simulation data"
        })

    # No existing simulation found, generate new one via LLM
    print(f"🔍 No existing simulation found for document {pk}, generating new one...")
    
    # Run extraction (LLM) to produce a structured JSON based on document content
    try:
        from ai_models.run_simulation_models_extraction import run_extraction
        # Pass document content to the extraction
        document_content = doc.payload.get('full_text', '') if doc.payload else ''
        print(f"🔍 Document content length: {len(document_content)}")
        print(f"🔍 Document content preview: {document_content[:200]}...")
        extracted = run_extraction(document_content=document_content)
        print(f"🤖 LLM extracted data: {extracted}")
    except Exception as exc:  # noqa: BLE001
        # Return error instead of mock data
        print(f"❌ Simulation extraction failed: {exc}")
        return JsonResponse({
            "error": "Simulation generation failed",
            "message": "Unable to generate simulation data. Please try again later.",
            "details": str(exc)
        }, status=500)

    # Map extracted JSON to our import payload shape using LLM data
    session_data = extracted.get("session", {})
    session_payload = {
        "document_id": doc.id,
        "session": {
            "title": session_data.get("title", f"Simulation for {doc.file_name}"),
            "scenario": session_data.get("scenario", "normal"),
            "parameters": session_data.get("parameters", {"source": "llm_extraction"}),
            "jurisdiction": session_data.get("jurisdiction", ""),
            "jurisdiction_note": session_data.get("jurisdiction_note", ""),
        },
        "timeline": extracted.get("timeline", []),
        "penalty_forecast": extracted.get("penalty_forecast", []),
        "exit_comparisons": extracted.get("exit_comparisons", []),
        "narratives": extracted.get("narratives", []),
        "long_term": extracted.get("long_term", []),
        "risk_alerts": extracted.get("risk_alerts", []),
    }

    # Try to infer some defaults from enums/relationships if provided (best-effort)
    # For now, we leave those arrays empty unless you want me to create mock data from the model definitions.

    # Persist via the same code path as manual import
    request._body = json.dumps(session_payload).encode("utf-8")  # type: ignore[attr-defined]
    result = import_simulation_view(request)
    
    # If successful, add metadata to indicate this is a new simulation
    if isinstance(result, JsonResponse) and result.status_code == 200:
        response_data = json.loads(result.content.decode('utf-8'))
        response_data['cached'] = False
        response_data['message'] = 'New simulation generated'
        return JsonResponse(response_data)
    
    return result


@csrf_exempt
@transaction.atomic
def import_simulation_view(request: HttpRequest):
    """Accepts a JSON payload describing a simulation and persists related models.

    Expected JSON (minimal):
    {
      "document_id": 1,
      "session": {
        "title": "...",
        "scenario": "normal",
        "parameters": {...},
        "jurisdiction": "...",
        "jurisdiction_note": "..."
      },
      "timeline": [ {"order": 1, "title": "...", "description": "...", "detailed_description": "...", "risks": []} ],
      "penalty_forecast": [ {"label": "Month 1", "base_amount": 0, "fees_amount": 0, "penalties_amount": 0, "total_amount": 0} ],
      "exit_comparisons": [ {"label": "Exit at 6 months", "penalty_text": "₹25,000", "risk_level": "medium", "benefits_lost": "..."} ],
      "narratives": [ {"title": "...", "subtitle": "...", "narrative": "...", "severity": "low", "key_points": [], "financial_impact": []} ],
      "long_term": [ {"index": 0, "label": "Month 0", "value": 0} ],
      "risk_alerts": [ {"level": "info", "message": "..."} ]
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)

    doc_id = payload.get("document_id")
    if not doc_id:
        return JsonResponse({"error": "document_id is required"}, status=400)

    document = get_object_or_404(ParsedDocument, pk=doc_id)

    from .models import (
        SimulationSession,
        SimulationTimelineNode,
        SimulationPenaltyForecast,
        SimulationExitComparison,
        SimulationNarrativeOutcome,
        SimulationLongTermPoint,
        SimulationRiskAlert,
    )

    session_data = payload.get("session") or {}
    session = SimulationSession.objects.create(
        document=document,
        title=str(session_data.get("title", ""))[:255],
        scenario=str(session_data.get("scenario", "normal"))[:32],
        parameters=session_data.get("parameters") or {},
        jurisdiction=str(session_data.get("jurisdiction", ""))[:128],
        jurisdiction_note=str(session_data.get("jurisdiction_note", "")),
    )

    for node in payload.get("timeline", []) or []:
        SimulationTimelineNode.objects.create(
            session=session,
            order=int(node.get("order") or 0),
            title=str(node.get("title", ""))[:255],
            description=str(node.get("description", ""))[:512],
            detailed_description=str(node.get("detailed_description", "")),
            risks=node.get("risks") or [],
        )

    for row in payload.get("penalty_forecast", []) or []:
        SimulationPenaltyForecast.objects.create(
            session=session,
            label=str(row.get("label", f"Month {row.get('month', 1)}"))[:64],
            base_amount=float(row.get("base_amount", 0)),
            fees_amount=float(row.get("fees_amount", 0)),
            penalties_amount=float(row.get("penalties_amount", 0)),
            total_amount=float(row.get("total_amount", 0)),
        )

    for item in payload.get("exit_comparisons", []) or []:
        SimulationExitComparison.objects.create(
            session=session,
            label=str(item.get("label", ""))[:128],
            penalty_text=str(item.get("penalty_text", ""))[:64],
            risk_level=str(item.get("risk_level", "low"))[:16],
            benefits_lost=str(item.get("benefits_lost", ""))[:128],
        )

    for item in payload.get("narratives", []) or []:
        SimulationNarrativeOutcome.objects.create(
            session=session,
            title=str(item.get("title", ""))[:255],
            subtitle=str(item.get("subtitle", ""))[:255],
            narrative=str(item.get("narrative", "")),
            severity=str(item.get("severity", "low"))[:16],
            key_points=item.get("key_points") or [],
            financial_impact=[item.get("financial_impact", "")] if isinstance(item.get("financial_impact"), str) else (item.get("financial_impact") or []),
        )

    for item in payload.get("long_term", []) or []:
        SimulationLongTermPoint.objects.create(
            session=session,
            index=int(item.get("index") or 0),
            label=str(item.get("label", ""))[:64],
            value=item.get("value") or 0,
            description=str(item.get("description", ""))[:255],
        )

    for item in payload.get("risk_alerts", []) or []:
        SimulationRiskAlert.objects.create(
            session=session,
            level=str(item.get("level", "info"))[:16],
            message=str(item.get("message", ""))[:512],
        )

    return JsonResponse({"status": "ok", "session_id": session.id})


def simulation_detail_view(request: HttpRequest, pk: int):
    """Fetch simulation session and all related data."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    from .models import (
        SimulationSession,
        SimulationTimelineNode,
        SimulationPenaltyForecast,
        SimulationExitComparison,
        SimulationNarrativeOutcome,
        SimulationLongTermPoint,
        SimulationRiskAlert,
    )

    session = get_object_or_404(SimulationSession, pk=pk)

    # Fetch all related data
    timeline_nodes = SimulationTimelineNode.objects.filter(session=session).order_by('order')
    penalty_forecasts = SimulationPenaltyForecast.objects.filter(session=session).order_by('id')
    exit_comparisons = SimulationExitComparison.objects.filter(session=session).order_by('id')
    narratives = SimulationNarrativeOutcome.objects.filter(session=session).order_by('id')
    long_term_points = SimulationLongTermPoint.objects.filter(session=session).order_by('index')
    risk_alerts = SimulationRiskAlert.objects.filter(session=session).order_by('id')

    # Build response
    response_data = {
        "session": {
            "id": session.id,
            "title": session.title,
            "scenario": session.scenario,
            "parameters": session.parameters,
            "jurisdiction": session.jurisdiction,
            "jurisdiction_note": session.jurisdiction_note,
            "created_at": session.created_at.isoformat(),
        },
        "timeline": [
            {
                "id": node.id,
                "order": node.order,
                "title": node.title,
                "description": node.description,
                "detailed_description": node.detailed_description,
                "risks": node.risks,
            }
            for node in timeline_nodes
        ],
        "penalty_forecast": [
            {
                "id": forecast.id,
                "label": forecast.label,
                "base_amount": float(forecast.base_amount),
                "fees_amount": float(forecast.fees_amount),
                "penalties_amount": float(forecast.penalties_amount),
                "total_amount": float(forecast.total_amount),
            }
            for forecast in penalty_forecasts
        ],
        "exit_comparisons": [
            {
                "id": comp.id,
                "label": comp.label,
                "penalty_text": comp.penalty_text,
                "risk_level": comp.risk_level,
                "benefits_lost": comp.benefits_lost,
            }
            for comp in exit_comparisons
        ],
        "narratives": [
            {
                "id": narrative.id,
                "title": narrative.title,
                "subtitle": narrative.subtitle,
                "narrative": narrative.narrative,
                "severity": narrative.severity,
                "key_points": narrative.key_points,
                "financial_impact": narrative.financial_impact,
            }
            for narrative in narratives
        ],
        "long_term": [
            {
                "id": point.id,
                "index": point.index,
                "label": point.label,
                "value": float(point.value),
                "description": point.description,
            }
            for point in long_term_points
        ],
        "risk_alerts": [
            {
                "id": alert.id,
                "level": alert.level,
                "message": alert.message,
            }
            for alert in risk_alerts
        ],
    }

    return JsonResponse(response_data)


def document_simulations_view(request: HttpRequest, pk: int):
    """Check if a document has existing simulations."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    doc = get_object_or_404(ParsedDocument, pk=pk)
    
    from .models import SimulationSession
    simulations = SimulationSession.objects.filter(document=doc).order_by('-created_at')
    
    response_data = {
        "document_id": doc.id,
        "has_simulations": simulations.exists(),
        "simulation_count": simulations.count(),
        "latest_simulation": None,
    }
    
    if simulations.exists():
        latest = simulations.first()
        response_data["latest_simulation"] = {
            "id": latest.id,
            "title": latest.title,
            "scenario": latest.scenario,
            "created_at": latest.created_at.isoformat(),
        }
    
    return JsonResponse(response_data)


@csrf_exempt
def translate_document_view(request: HttpRequest, pk: int):
    """Translate a document to a specific language."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)
    
    target_language = payload.get("language", "en")
    if target_language not in ['en', 'hi', 'ta', 'te']:
        return JsonResponse({"error": "Invalid language code"}, status=400)
    
    doc = get_object_or_404(ParsedDocument, pk=pk)
    
    # Check if translation already exists
    existing_translation = DocumentTranslation.objects.filter(
        document=doc, 
        language=target_language
    ).first()
    
    if existing_translation:
        return JsonResponse({
            "status": "ok",
            "translation_id": existing_translation.id,
            "language": existing_translation.language,
            "cached": True,
            "message": "Translation already exists"
        })
    
    # Create new translation
    try:
        translator = DocumentTranslator()
        target_lang_code = translator.get_language_code(target_language)
        
        # Get original document data
        original_pages = doc.payload.get('pages', [])
        original_full_text = doc.payload.get('full_text', '')
        
        # Translate pages
        translated_pages = translator.translate_pages(original_pages, target_lang_code)
        
        # Translate full text
        translated_full_text = translator.translate_full_text(original_full_text, target_lang_code)
        
        # Create translation record
        translation = DocumentTranslation.objects.create(
            document=doc,
            language=target_language,
            translated_pages=translated_pages,
            translated_full_text=translated_full_text
        )
        
        return JsonResponse({
            "status": "ok",
            "translation_id": translation.id,
            "language": translation.language,
            "cached": False,
            "message": "Translation created successfully"
        })
        
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({
            "error": "Translation failed",
            "message": "Unable to translate document. Please try again later.",
            "details": str(exc)
        }, status=500)


def get_document_translation_view(request: HttpRequest, pk: int, language: str):
    """Get translated document content."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    if language not in ['en', 'hi', 'ta', 'te']:
        return JsonResponse({"error": "Invalid language code"}, status=400)
    
    doc = get_object_or_404(ParsedDocument, pk=pk)
    
    # If requesting English, return original document
    if language == 'en':
        data = dict(doc.payload)
        data["id"] = doc.id
        data["file_name"] = doc.file_name
        data["num_pages"] = doc.num_pages
        data["file_url"] = doc.uploaded_file.url if doc.uploaded_file else None
        data["analysis_available"] = hasattr(doc, "analysis") and doc.analysis.status == "success"
        data["language"] = "en"
        return JsonResponse(data)
    
    # Get translation
    translation = DocumentTranslation.objects.filter(
        document=doc, 
        language=language
    ).first()
    
    if not translation:
        return JsonResponse({
            "error": "Translation not found",
            "message": f"Document not translated to {language}. Please request translation first."
        }, status=404)
    
    # Return translated data
    data = {
        "id": doc.id,
        "file_name": doc.file_name,
        "num_pages": doc.num_pages,
        "file_url": doc.uploaded_file.url if doc.uploaded_file else None,
        "analysis_available": hasattr(doc, "analysis") and doc.analysis.status == "success",
        "language": language,
        "pages": translation.translated_pages,
        "full_text": translation.translated_full_text,
        "num_pages": len(translation.translated_pages)
    }
    
    return JsonResponse(data)


def list_document_translations_view(request: HttpRequest, pk: int):
    """List all available translations for a document."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    doc = get_object_or_404(ParsedDocument, pk=pk)
    
    translations = DocumentTranslation.objects.filter(document=doc).values(
        'id', 'language', 'created_at', 'updated_at'
    )
    
    return JsonResponse({
        "document_id": doc.id,
        "available_translations": list(translations),
        "total_translations": translations.count()
    })


@csrf_exempt
def chat_gemini_view(request: HttpRequest):
    """Proxy endpoint that forwards chat prompts to Google Gemini.

    Request JSON:
    { "prompt": "Hello" , "model": "gemini-2.0-flash", "thinking_budget": 0 }

    Response JSON:
    { "text": "..." }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as exc:
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)

    prompt = (payload.get("prompt") or "").strip()
    model = payload.get("model") or None
    thinking_budget = payload.get("thinking_budget")
    system_instruction = payload.get("system_instruction") or _GEMINI_SYSTEM_PROMPT
    if not prompt:
        return JsonResponse({"error": "prompt is required"}, status=400)

    try:
        client = GoogleGeminiAPI()
        text = client.generate_text(
            prompt,
            model=model,
            thinking_budget=thinking_budget,
            system_instruction=system_instruction,
        )

        # Optional server-side translation of AI output
        target_language = (payload.get("language") or "en").lower()
        if target_language and target_language != "en":
            try:
                translator = DocumentTranslator()
                text = translator.translate_text(text, target_language, 'en')
            except Exception:
                pass

        return JsonResponse({"text": text})
    except (ValueError, GeminiAPIError) as exc:  # missing key or API error
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def translate_analysis_view(request: HttpRequest, pk: int):
    """Translate document analysis to a specific language."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        payload = json.loads(request.body)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": f"Invalid JSON: {exc}"}, status=400)
    
    target_language = payload.get("language", "en")
    if target_language not in ['en', 'hi', 'ta', 'te']:
        return JsonResponse({"error": "Invalid language code"}, status=400)
    
    analysis = get_object_or_404(DocumentAnalysis, pk=pk)
    
    # Check if translation already exists
    existing_translation = DocumentAnalysisTranslation.objects.filter(
        analysis=analysis, language=target_language
    ).first()
    
    if existing_translation:
        return JsonResponse({
            "message": "Translation already exists",
            "translation_id": existing_translation.id,
            "language": target_language
        })
    
    # If requesting English, return original analysis
    if target_language == 'en':
        return JsonResponse({
            "message": "Original analysis returned",
            "analysis": analysis.output_json,
            "language": "en"
        })
    
    # Translate the analysis
    translator = DocumentTranslator()
    original_analysis = analysis.output_json or {}
    
    try:
        translated_analysis = translator.translate_analysis_json(
            original_analysis, target_language, 'en'
        )
        
        # Save the translation
        translation = DocumentAnalysisTranslation.objects.create(
            analysis=analysis,
            language=target_language,
            translated_analysis_json=translated_analysis
        )
        
        return JsonResponse({
            "message": "Analysis translated successfully",
            "translation_id": translation.id,
            "language": target_language,
            "analysis": translated_analysis
        })
        
    except Exception as e:
        return JsonResponse({"error": f"Translation failed: {str(e)}"}, status=500)


def get_analysis_translation_view(request: HttpRequest, pk: int, language: str):
    """Get translated analysis for a specific language."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    if language not in ['en', 'hi', 'ta', 'te']:
        return JsonResponse({"error": "Invalid language code"}, status=400)
    
    analysis = get_object_or_404(DocumentAnalysis, pk=pk)
    
    # If requesting English, return original analysis
    if language == 'en':
        return JsonResponse({
            "analysis": analysis.output_json,
            "language": "en",
            "is_original": True
        })
    
    # Try to get existing translation
    translation = DocumentAnalysisTranslation.objects.filter(
        analysis=analysis, language=language
    ).first()
    
    if translation:
        return JsonResponse({
            "analysis": translation.translated_analysis_json,
            "language": language,
            "is_original": False,
            "translation_id": translation.id
        })
    
    return JsonResponse({"error": "Translation not found"}, status=404)


def list_analysis_translations_view(request: HttpRequest, pk: int):
    """List all available translations for a document analysis."""
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    analysis = get_object_or_404(DocumentAnalysis, pk=pk)
    translations = DocumentAnalysisTranslation.objects.filter(analysis=analysis)
    
    translation_list = [
        {
            "id": t.id,
            "language": t.language,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat()
        }
        for t in translations
    ]
    
    return JsonResponse({
        "analysis_id": analysis.id,
        "available_translations": translation_list,
        "total_translations": translations.count()
    })


def _translate_document_async(document_id: int, document_data: dict):
    """Background function to translate document content for all languages."""
    def translate_worker():
        try:
            doc = ParsedDocument.objects.get(id=document_id)
            translator = DocumentTranslator()
            supported_languages = ['hi', 'ta', 'te']
            
            for lang in supported_languages:
                try:
                    # Check if translation already exists
                    if DocumentTranslation.objects.filter(document=doc, language=lang).exists():
                        continue
                    
                    # Get original document data
                    original_pages = document_data.get('pages', [])
                    original_full_text = document_data.get('full_text', '')
                    
                    # Translate pages
                    translated_pages = translator.translate_pages(original_pages, lang)
                    
                    # Translate full text
                    translated_full_text = translator.translate_full_text(original_full_text, lang)
                    
                    # Create translation record
                    DocumentTranslation.objects.create(
                        document=doc,
                        language=lang,
                        translated_pages=translated_pages,
                        translated_full_text=translated_full_text
                    )
                    
                    print(f"✅ Document {document_id} translated to {lang}")
                except Exception as e:
                    print(f"❌ Failed to translate document {document_id} to {lang}: {e}")
        except Exception as e:
            print(f"❌ Background document translation failed for {document_id}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=translate_worker)
    thread.daemon = True
    thread.start()


def _analyze_document_async(document_id: int, document_data: dict):
    """Background function to analyze document content."""
    def analyze_worker():
        try:
            doc = ParsedDocument.objects.get(id=document_id)
            meta = {"file_name": doc.file_name, "num_pages": doc.num_pages}
            pages = [p.get("text", "") for p in document_data.get("pages", [])]
            
            # Call OpenRouter API for analysis
            analysis_payload = call_openrouter_for_analysis(pages, meta)
            
            # Create analysis record
            analysis_obj, _ = DocumentAnalysis.objects.update_or_create(
                document=doc,
                defaults={
                    "status": "success" if analysis_payload else "failed",
                    "output_json": analysis_payload or {},
                    "model": "openrouter",
                },
            )
            
            # Trigger translations if analysis was successful
            if analysis_obj and analysis_obj.status == "success":
                try:
                    # Translate document content for all languages
                    _translate_document_async(doc.id, document_data)
                    # Translate analysis for all languages
                    _translate_analysis_async(analysis_obj.id, analysis_obj.output_json)
                except Exception as exc:  # noqa: BLE001
                    print(f"Background translation failed for document {doc.id}: {exc}")
            
            print(f"✅ Document {document_id} analysis completed")
            
        except Exception as e:
            print(f"❌ Background analysis failed for document {document_id}: {e}")
            # Create failed analysis record
            try:
                doc = ParsedDocument.objects.get(id=document_id)
                DocumentAnalysis.objects.update_or_create(
                    document=doc,
                    defaults={"status": "failed", "error": str(e)},
                )
            except Exception:
                pass
    
    # Run in background thread
    thread = threading.Thread(target=analyze_worker)
    thread.daemon = True
    thread.start()


def _translate_analysis_async(analysis_id: int, analysis_json: dict):
    """Background function to translate analysis for all languages."""
    def translate_worker():
        try:
            analysis = DocumentAnalysis.objects.get(id=analysis_id)
            translator = DocumentTranslator()
            supported_languages = ['hi', 'ta', 'te']
            
            for lang in supported_languages:
                try:
                    # Check if translation already exists
                    if DocumentAnalysisTranslation.objects.filter(analysis=analysis, language=lang).exists():
                        continue
                    
                    # Translate the analysis
                    translated_analysis = translator.translate_analysis_json(
                        analysis_json, lang, 'en'
                    )
                    
                    # Create translation record
                    DocumentAnalysisTranslation.objects.create(
                        analysis=analysis,
                        language=lang,
                        translated_analysis_json=translated_analysis
                    )
                    
                    print(f"✅ Analysis {analysis_id} translated to {lang}")
                except Exception as e:
                    print(f"❌ Failed to translate analysis {analysis_id} to {lang}: {e}")
        except Exception as e:
            print(f"❌ Background analysis translation failed for {analysis_id}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=translate_worker)
    thread.daemon = True
    thread.start()


def _analyze_document_async(document_id: int, document_data: dict):
    """Background function to analyze document content."""
    def analyze_worker():
        try:
            doc = ParsedDocument.objects.get(id=document_id)
            meta = {"file_name": doc.file_name, "num_pages": doc.num_pages}
            pages = [p.get("text", "") for p in document_data.get("pages", [])]
            
            # Call OpenRouter API for analysis
            analysis_payload = call_openrouter_for_analysis(pages, meta)
            
            # Create analysis record
            analysis_obj, _ = DocumentAnalysis.objects.update_or_create(
                document=doc,
                defaults={
                    "status": "success" if analysis_payload else "failed",
                    "output_json": analysis_payload or {},
                    "model": "openrouter",
                },
            )
            
            # Trigger translations if analysis was successful
            if analysis_obj and analysis_obj.status == "success":
                try:
                    # Translate document content for all languages
                    _translate_document_async(doc.id, document_data)
                    # Translate analysis for all languages
                    _translate_analysis_async(analysis_obj.id, analysis_obj.output_json)
                except Exception as exc:  # noqa: BLE001
                    print(f"Background translation failed for document {doc.id}: {exc}")
            
            print(f"✅ Document {document_id} analysis completed")
            
        except Exception as e:
            print(f"❌ Background analysis failed for document {document_id}: {e}")
            # Create failed analysis record
            try:
                doc = ParsedDocument.objects.get(id=document_id)
                DocumentAnalysis.objects.update_or_create(
                    document=doc,
                    defaults={"status": "failed", "error": str(e)},
                )
            except Exception:
                pass
    
    # Run in background thread
    thread = threading.Thread(target=analyze_worker)
    thread.daemon = True
    thread.start()


# Simulation Translation Views

@csrf_exempt
def translate_simulation_view(request: HttpRequest, session_id: int):
    """Translate simulation session data to a specific language."""
    print(f"🔄 translate_simulation_view called for session {session_id}")
    
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        target_language = data.get('language', 'hi')
        print(f"📝 Target language: {target_language}")
        
        if target_language not in ['hi', 'ta', 'te']:
            return JsonResponse({"error": "Unsupported language"}, status=400)
        
        session = get_object_or_404(SimulationSession, id=session_id)
        print(f"📋 Session found: {session.title}")
        
        # Check if translation already exists
        session_translation_exists = SimulationSessionTranslation.objects.filter(session=session, language=target_language).exists()
        if session_translation_exists:
            print(f"✅ Session translation already exists for {target_language}")
            # Still translate related data even if session translation exists
            _translate_simulation_related_data_sync(session_id, target_language)
            return JsonResponse({"message": "Translation already exists"})
        
        translator = DocumentTranslator()
        
        # Get session data
        session_data = {
            'title': session.title,
            'jurisdiction': session.jurisdiction,
            'jurisdiction_note': session.jurisdiction_note,
        }
        print(f"📄 Session data: {session_data}")
        
        # Translate session data
        translated_session = translator.translate_simulation_session(session_data, target_language, 'en')
        print(f"🌐 Translated session: {translated_session}")
        
        # Create translation record
        SimulationSessionTranslation.objects.create(
            session=session,
            language=target_language,
            translated_title=translated_session.get('title', ''),
            translated_jurisdiction=translated_session.get('jurisdiction', ''),
            translated_jurisdiction_note=translated_session.get('jurisdiction_note', ''),
        )
        print(f"💾 Translation record created for {target_language}")
        
        # Translate related data (synchronous for now to debug)
        _translate_simulation_related_data_sync(session_id, target_language)
        
        return JsonResponse({"message": "Translation started"})
        
    except Exception as e:
        print(f"❌ Translation error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def get_simulation_translation_view(request: HttpRequest, session_id: int, language: str):
    """Get translated simulation data for a specific language."""
    print(f"🔄 get_simulation_translation_view called for session {session_id}, language {language}")
    
    try:
        session = get_object_or_404(SimulationSession, id=session_id)
        print(f"📋 Session found: {session.title}")
        
        # Get or create translation
        translation, created = SimulationSessionTranslation.objects.get_or_create(
            session=session,
            language=language,
            defaults={
                'translated_title': session.title,
                'translated_jurisdiction': session.jurisdiction,
                'translated_jurisdiction_note': session.jurisdiction_note,
            }
        )
        
        # If translation was just created, trigger background translation
        if created and language != 'en':
            _translate_simulation_related_data_async(session_id, language)
        
        # Build translated simulation data
        translated_data = {
            'session': {
                'id': session.id,
                'title': translation.translated_title,
                'scenario': session.scenario,
                'parameters': session.parameters,
                'jurisdiction': translation.translated_jurisdiction,
                'jurisdiction_note': translation.translated_jurisdiction_note,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
            }
        }
        
        # Add translated timeline nodes
        timeline_nodes = session.timeline.all()
        translated_timeline = []
        for node in timeline_nodes:
            node_translation = SimulationTimelineNodeTranslation.objects.filter(
                node=node, language=language
            ).first()
            
            if node_translation:
                translated_timeline.append({
                    'id': node.id,
                    'order': node.order,
                    'title': node_translation.translated_title,
                    'description': node_translation.translated_description,
                    'detailed_description': node_translation.translated_detailed_description,
                    'risks': node_translation.translated_risks,
                })
            else:
                translated_timeline.append({
                    'id': node.id,
                    'order': node.order,
                    'title': node.title,
                    'description': node.description,
                    'detailed_description': node.detailed_description,
                    'risks': node.risks,
                })
        
        translated_data['timeline'] = translated_timeline
        
        # Add translated penalty forecasts
        penalty_forecasts = session.penalty_forecast.all()
        translated_forecasts = []
        for forecast in penalty_forecasts:
            forecast_translation = SimulationPenaltyForecastTranslation.objects.filter(
                forecast=forecast, language=language
            ).first()
            
            translated_forecasts.append({
                'id': forecast.id,
                'label': forecast_translation.translated_label if forecast_translation else forecast.label,
                'base_amount': float(forecast.base_amount),
                'fees_amount': float(forecast.fees_amount),
                'penalties_amount': float(forecast.penalties_amount),
                'total_amount': float(forecast.total_amount),
            })
        
        translated_data['penalty_forecast'] = translated_forecasts
        
        # Add translated exit comparisons
        exit_comparisons = session.exit_comparisons.all()
        translated_comparisons = []
        for comparison in exit_comparisons:
            comparison_translation = SimulationExitComparisonTranslation.objects.filter(
                comparison=comparison, language=language
            ).first()
            
            translated_comparisons.append({
                'id': comparison.id,
                'label': comparison_translation.translated_label if comparison_translation else comparison.label,
                'penalty_text': comparison_translation.translated_penalty_text if comparison_translation else comparison.penalty_text,
                'risk_level': comparison.risk_level,
                'benefits_lost': comparison_translation.translated_benefits_lost if comparison_translation else comparison.benefits_lost,
            })
        
        translated_data['exit_comparisons'] = translated_comparisons
        
        # Add translated narrative outcomes
        narrative_outcomes = session.narratives.all()
        translated_narratives = []
        for outcome in narrative_outcomes:
            outcome_translation = SimulationNarrativeOutcomeTranslation.objects.filter(
                outcome=outcome, language=language
            ).first()
            
            translated_narratives.append({
                'id': outcome.id,
                'title': outcome_translation.translated_title if outcome_translation else outcome.title,
                'subtitle': outcome_translation.translated_subtitle if outcome_translation else outcome.subtitle,
                'narrative': outcome_translation.translated_narrative if outcome_translation else outcome.narrative,
                'severity': outcome.severity,
                'key_points': outcome_translation.translated_key_points if outcome_translation else outcome.key_points,
                'financial_impact': outcome_translation.translated_financial_impact if outcome_translation else outcome.financial_impact,
            })
        
        translated_data['narratives'] = translated_narratives
        
        # Add translated long-term points
        long_term_points = session.long_term.all()
        translated_points = []
        for point in long_term_points:
            point_translation = SimulationLongTermPointTranslation.objects.filter(
                point=point, language=language
            ).first()
            
            translated_points.append({
                'id': point.id,
                'index': point.index,
                'label': point_translation.translated_label if point_translation else point.label,
                'value': float(point.value),
                'description': point_translation.translated_description if point_translation else point.description,
            })
        
        translated_data['long_term'] = translated_points
        
        # Add translated risk alerts
        risk_alerts = session.risk_alerts.all()
        translated_alerts = []
        print(f"📊 Getting risk alerts for session {session_id}: {risk_alerts.count()} alerts")
        for alert in risk_alerts:
            alert_translation = SimulationRiskAlertTranslation.objects.filter(
                alert=alert, language=language
            ).first()
            
            message = alert_translation.translated_message if alert_translation else alert.message
            print(f"📊 Risk alert {alert.id}: level={alert.level}, message={message[:50]}...")
            
            translated_alerts.append({
                'id': alert.id,
                'level': alert.level,
                'message': message,
                'created_at': alert.created_at.isoformat(),
            })
        
        translated_data['risk_alerts'] = translated_alerts
        print(f"📊 Final risk alerts count: {len(translated_alerts)}")
        
        return JsonResponse(translated_data)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def list_simulation_translations_view(request: HttpRequest, session_id: int):
    """List all available translations for a simulation session."""
    try:
        session = get_object_or_404(SimulationSession, id=session_id)
        translations = SimulationSessionTranslation.objects.filter(session=session)
        
        available_languages = [{'language': t.language, 'created_at': t.created_at.isoformat()} for t in translations]
        
        return JsonResponse({"available_languages": available_languages})
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def _translate_simulation_related_data_sync(session_id: int, target_language: str):
    """Synchronous function to translate all simulation related data."""
    try:
        print(f"🔄 Synchronous translation started for session {session_id}, language {target_language}")
        session = SimulationSession.objects.get(id=session_id)
        translator = DocumentTranslator()
        print(f"📋 Session found: {session.title}")
        
        # Translate timeline nodes
        for node in session.timeline.all():
            try:
                if not SimulationTimelineNodeTranslation.objects.filter(node=node, language=target_language).exists():
                    # Safely translate risks list item-by-item (avoid JSON roundtrip)
                    risks_list = node.risks if isinstance(node.risks, list) else []
                    translated_risks: list = []
                    for r in risks_list:
                        try:
                            translated_risks.append(translator.translate_text(str(r), target_language, 'en'))
                        except Exception:
                            translated_risks.append(str(r))

                    SimulationTimelineNodeTranslation.objects.create(
                        node=node,
                        language=target_language,
                        translated_title=translator.translate_text(node.title, target_language, 'en'),
                        translated_description=translator.translate_text(node.description, target_language, 'en'),
                        translated_detailed_description=translator.translate_text(node.detailed_description, target_language, 'en'),
                        translated_risks=translated_risks,
                    )
                    print(f"💾 Created timeline translation for node {node.id}")
            except Exception as e:
                print(f"❌ Failed timeline translation for node {node.id}: {e}")
        
        # Translate penalty forecasts
        for forecast in session.penalty_forecast.all():
            if not SimulationPenaltyForecastTranslation.objects.filter(forecast=forecast, language=target_language).exists():
                SimulationPenaltyForecastTranslation.objects.create(
                    forecast=forecast,
                    language=target_language,
                    translated_label=translator.translate_text(forecast.label, target_language, 'en'),
                )
                print(f"💾 Created penalty forecast translation for {forecast.id}")
        
        # Translate exit comparisons
        for comparison in session.exit_comparisons.all():
            if not SimulationExitComparisonTranslation.objects.filter(comparison=comparison, language=target_language).exists():
                SimulationExitComparisonTranslation.objects.create(
                    comparison=comparison,
                    language=target_language,
                    translated_label=translator.translate_text(comparison.label, target_language, 'en'),
                    translated_penalty_text=translator.translate_text(comparison.penalty_text, target_language, 'en'),
                    translated_benefits_lost=translator.translate_text(comparison.benefits_lost, target_language, 'en'),
                )
                print(f"💾 Created exit comparison translation for {comparison.id}")
        
        # Translate narrative outcomes
        for outcome in session.narratives.all():
            try:
                if not SimulationNarrativeOutcomeTranslation.objects.filter(outcome=outcome, language=target_language).exists():
                    translated_key_points = []
                    for point in (outcome.key_points or []):
                        try:
                            translated_key_points.append(translator.translate_text(point, target_language, 'en'))
                        except Exception:
                            translated_key_points.append(point)

                    translated_financial_impact = []
                    for impact in (outcome.financial_impact or []):
                        try:
                            translated_financial_impact.append(translator.translate_text(impact, target_language, 'en'))
                        except Exception:
                            translated_financial_impact.append(impact)
                    
                    SimulationNarrativeOutcomeTranslation.objects.create(
                        outcome=outcome,
                        language=target_language,
                        translated_title=translator.translate_text(outcome.title, target_language, 'en'),
                        translated_subtitle=translator.translate_text(outcome.subtitle, target_language, 'en'),
                        translated_narrative=translator.translate_text(outcome.narrative, target_language, 'en'),
                        translated_key_points=translated_key_points,
                        translated_financial_impact=translated_financial_impact,
                    )
                    print(f"💾 Created narrative translation for {outcome.id}")
            except Exception as e:
                print(f"❌ Failed narrative translation for outcome {outcome.id}: {e}")
        
        # Translate long-term points
        for point in session.long_term.all():
            if not SimulationLongTermPointTranslation.objects.filter(point=point, language=target_language).exists():
                SimulationLongTermPointTranslation.objects.create(
                    point=point,
                    language=target_language,
                    translated_label=translator.translate_text(point.label, target_language, 'en'),
                    translated_description=translator.translate_text(point.description, target_language, 'en'),
                )
                print(f"💾 Created long-term point translation for {point.id}")
        
        # Translate risk alerts
        risk_alerts = session.risk_alerts.all()
        print(f"📊 Found {risk_alerts.count()} risk alerts for session {session_id}")
        for alert in risk_alerts:
            print(f"📊 Risk alert: level={alert.level}, message={alert.message[:50]}...")
            if not SimulationRiskAlertTranslation.objects.filter(alert=alert, language=target_language).exists():
                translated_message = translator.translate_text(alert.message, target_language, 'en')
                print(f"🌐 Translated message: {translated_message[:50]}...")
                SimulationRiskAlertTranslation.objects.create(
                    alert=alert,
                    language=target_language,
                    translated_message=translated_message,
                )
                print(f"💾 Created translation for alert {alert.id}")
            else:
                print(f"✅ Translation already exists for alert {alert.id}")
        
        print(f"✅ Synchronous translation completed for session {session_id}")
        
    except Exception as e:
        print(f"❌ Synchronous translation failed for {session_id}: {e}")


def _translate_simulation_related_data_async(session_id: int, target_language: str):
    """Background function to translate all simulation related data."""
    def translate_worker():
        try:
            print(f"🔄 Background translation started for session {session_id}, language {target_language}")
            session = SimulationSession.objects.get(id=session_id)
            translator = DocumentTranslator()
            print(f"📋 Session found: {session.title}")
            
            # Translate timeline nodes
            for node in session.timeline.all():
                if not SimulationTimelineNodeTranslation.objects.filter(node=node, language=target_language).exists():
                    # translate risks item-wise safely
                    risks_list = node.risks if isinstance(node.risks, list) else []
                    safe_translated = []
                    for r in risks_list:
                        try:
                            safe_translated.append(translator.translate_text(str(r), target_language, 'en'))
                        except Exception:
                            safe_translated.append(str(r))
                    SimulationTimelineNodeTranslation.objects.create(
                        node=node,
                        language=target_language,
                        translated_title=translator.translate_text(node.title, target_language, 'en'),
                        translated_description=translator.translate_text(node.description, target_language, 'en'),
                        translated_detailed_description=translator.translate_text(node.detailed_description, target_language, 'en'),
                        translated_risks=safe_translated,
                    )
            
            # Translate penalty forecasts
            for forecast in session.penalty_forecast.all():
                if not SimulationPenaltyForecastTranslation.objects.filter(forecast=forecast, language=target_language).exists():
                    SimulationPenaltyForecastTranslation.objects.create(
                        forecast=forecast,
                        language=target_language,
                        translated_label=translator.translate_text(forecast.label, target_language, 'en'),
                    )
            
            # Translate exit comparisons
            for comparison in session.exit_comparisons.all():
                if not SimulationExitComparisonTranslation.objects.filter(comparison=comparison, language=target_language).exists():
                    SimulationExitComparisonTranslation.objects.create(
                        comparison=comparison,
                        language=target_language,
                        translated_label=translator.translate_text(comparison.label, target_language, 'en'),
                        translated_penalty_text=translator.translate_text(comparison.penalty_text, target_language, 'en'),
                        translated_benefits_lost=translator.translate_text(comparison.benefits_lost, target_language, 'en'),
                    )
            
            # Translate narrative outcomes
            for outcome in session.narratives.all():
                if not SimulationNarrativeOutcomeTranslation.objects.filter(outcome=outcome, language=target_language).exists():
                    translated_key_points = [
                        translator.translate_text(point, target_language, 'en')
                        for point in outcome.key_points
                    ] if outcome.key_points else []
                    
                    translated_financial_impact = [
                        translator.translate_text(impact, target_language, 'en')
                        for impact in outcome.financial_impact
                    ] if outcome.financial_impact else []
                    
                    SimulationNarrativeOutcomeTranslation.objects.create(
                        outcome=outcome,
                        language=target_language,
                        translated_title=translator.translate_text(outcome.title, target_language, 'en'),
                        translated_subtitle=translator.translate_text(outcome.subtitle, target_language, 'en'),
                        translated_narrative=translator.translate_text(outcome.narrative, target_language, 'en'),
                        translated_key_points=translated_key_points,
                        translated_financial_impact=translated_financial_impact,
                    )
            
            # Translate long-term points
            for point in session.long_term.all():
                if not SimulationLongTermPointTranslation.objects.filter(point=point, language=target_language).exists():
                    SimulationLongTermPointTranslation.objects.create(
                        point=point,
                        language=target_language,
                        translated_label=translator.translate_text(point.label, target_language, 'en'),
                        translated_description=translator.translate_text(point.description, target_language, 'en'),
                    )
            
            # Translate risk alerts
            risk_alerts = session.risk_alerts.all()
            print(f"📊 Found {risk_alerts.count()} risk alerts for session {session_id}")
            for alert in risk_alerts:
                print(f"📊 Risk alert: level={alert.level}, message={alert.message[:50]}...")
                if not SimulationRiskAlertTranslation.objects.filter(alert=alert, language=target_language).exists():
                    translated_message = translator.translate_text(alert.message, target_language, 'en')
                    print(f"🌐 Translated message: {translated_message[:50]}...")
                    SimulationRiskAlertTranslation.objects.create(
                        alert=alert,
                        language=target_language,
                        translated_message=translated_message,
                    )
                    print(f"💾 Created translation for alert {alert.id}")
                else:
                    print(f"✅ Translation already exists for alert {alert.id}")
            
            print(f"✅ Simulation {session_id} related data translated to {target_language}")
            
        except Exception as e:
            print(f"❌ Background simulation translation failed for {session_id}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=translate_worker)
    thread.daemon = True
    thread.start()


def _analyze_document_async(document_id: int, document_data: dict):
    """Background function to analyze document content."""
    def analyze_worker():
        try:
            doc = ParsedDocument.objects.get(id=document_id)
            meta = {"file_name": doc.file_name, "num_pages": doc.num_pages}
            pages = [p.get("text", "") for p in document_data.get("pages", [])]
            
            # Call OpenRouter API for analysis
            analysis_payload = call_openrouter_for_analysis(pages, meta)
            
            # Create analysis record
            analysis_obj, _ = DocumentAnalysis.objects.update_or_create(
                document=doc,
                defaults={
                    "status": "success" if analysis_payload else "failed",
                    "output_json": analysis_payload or {},
                    "model": "openrouter",
                },
            )
            
            # Trigger translations if analysis was successful
            if analysis_obj and analysis_obj.status == "success":
                try:
                    # Translate document content for all languages
                    _translate_document_async(doc.id, document_data)
                    # Translate analysis for all languages
                    _translate_analysis_async(analysis_obj.id, analysis_obj.output_json)
                except Exception as exc:  # noqa: BLE001
                    print(f"Background translation failed for document {doc.id}: {exc}")
            
            print(f"✅ Document {document_id} analysis completed")
            
        except Exception as e:
            print(f"❌ Background analysis failed for document {document_id}: {e}")
            # Create failed analysis record
            try:
                doc = ParsedDocument.objects.get(id=document_id)
                DocumentAnalysis.objects.update_or_create(
                    document=doc,
                    defaults={"status": "failed", "error": str(e)},
                )
            except Exception:
                pass
    
    # Run in background thread
    thread = threading.Thread(target=analyze_worker)
    thread.daemon = True
    thread.start()


