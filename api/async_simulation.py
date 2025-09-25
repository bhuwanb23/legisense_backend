import threading
from .models import ParsedDocument


def _generate_simulation_async(document_id: int, document_data: dict):
    """Background function to generate simulation data."""
    def simulation_worker():
        try:
            from ai_models.run_simulation_models_extraction import run_extraction
            
            doc = ParsedDocument.objects.get(id=document_id)
            print(f"🔄 Starting simulation generation for document {document_id}")
            
            # Get document content
            document_content = document_data.get('full_text', '') if document_data else ''
            print(f"🔍 Document content length: {len(document_content)}")
            
            # Run extraction with timeout protection
            try:
                extracted = run_extraction(document_content=document_content)
                print(f"🤖 LLM extracted data: {extracted}")
            except Exception as exc:
                print(f"❌ Simulation extraction failed: {exc}")
                # Use fallback data
                extracted = {
                    "session": {
                        "title": f"Simulation for {doc.file_name}",
                        "scenario": "normal",
                        "parameters": {"source": "fallback"},
                        "jurisdiction": "",
                        "jurisdiction_note": "",
                    },
                    "timeline": [],
                    "penalty_forecast": [],
                    "exit_comparisons": [],
                    "narratives": [],
                    "long_term": [],
                    "risk_alerts": [],
                }
            
            # Map extracted JSON to our import payload shape
            session_data = extracted.get("session", {})
            
            # Create simulation session directly to avoid circular imports
            from .models import (
                SimulationSession,
                SimulationTimelineNode,
                SimulationPenaltyForecast,
                SimulationExitComparison,
                SimulationNarrativeOutcome,
                SimulationLongTermPoint,
                SimulationRiskAlert,
            )
            
            # Create the session
            session = SimulationSession.objects.create(
                document=doc,
                title=str(session_data.get("title", f"Simulation for {doc.file_name}"))[:255],
                scenario=str(session_data.get("scenario", "normal"))[:32],
                parameters=session_data.get("parameters") or {},
                jurisdiction=str(session_data.get("jurisdiction", ""))[:128],
                jurisdiction_note=str(session_data.get("jurisdiction_note", "")),
            )
            
            # Create related objects
            for node in extracted.get("timeline", []) or []:
                SimulationTimelineNode.objects.create(
                    session=session,
                    order=int(node.get("order") or 0),
                    title=str(node.get("title", ""))[:255],
                    description=str(node.get("description", ""))[:512],
                    detailed_description=str(node.get("detailed_description", "")),
                    risks=node.get("risks") or [],
                )
            
            for row in extracted.get("penalty_forecast", []) or []:
                SimulationPenaltyForecast.objects.create(
                    session=session,
                    label=str(row.get("label", f"Month {row.get('month', 1)}"))[:64],
                    base_amount=float(row.get("base_amount", 0)),
                    fees_amount=float(row.get("fees_amount", 0)),
                    penalties_amount=float(row.get("penalties_amount", 0)),
                    total_amount=float(row.get("total_amount", 0)),
                )
            
            for item in extracted.get("exit_comparisons", []) or []:
                SimulationExitComparison.objects.create(
                    session=session,
                    label=str(item.get("label", ""))[:128],
                    penalty_text=str(item.get("penalty_text", ""))[:64],
                    risk_level=str(item.get("risk_level", "low"))[:16],
                    benefits_lost=str(item.get("benefits_lost", ""))[:128],
                )
            
            for item in extracted.get("narratives", []) or []:
                SimulationNarrativeOutcome.objects.create(
                    session=session,
                    title=str(item.get("title", ""))[:255],
                    subtitle=str(item.get("subtitle", ""))[:255],
                    narrative=str(item.get("narrative", "")),
                    severity=str(item.get("severity", "low"))[:16],
                    key_points=item.get("key_points") or [],
                    financial_impact=[item.get("financial_impact", "")] if isinstance(item.get("financial_impact"), str) else (item.get("financial_impact") or []),
                )
            
            for item in extracted.get("long_term", []) or []:
                SimulationLongTermPoint.objects.create(
                    session=session,
                    index=int(item.get("index") or 0),
                    label=str(item.get("label", ""))[:64],
                    value=item.get("value") or 0,
                    description=str(item.get("description", ""))[:255],
                )
            
            for item in extracted.get("risk_alerts", []) or []:
                SimulationRiskAlert.objects.create(
                    session=session,
                    level=str(item.get("level", "info"))[:16],
                    message=str(item.get("message", ""))[:512],
                )
            
            print(f"✅ Simulation generation completed for document {document_id}, session_id: {session.id}")
            
        except Exception as e:
            print(f"❌ Background simulation generation failed for document {document_id}: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=simulation_worker)
    thread.daemon = True
    thread.start()
