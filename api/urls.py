from django.urls import path

from .views import (
    parse_pdf_view,
    list_parsed_docs_view,
    parsed_doc_detail_view,
    parsed_doc_analysis_view,
    parsed_doc_analyze_view,
    parsed_doc_simulate_view,
    import_simulation_view,
    simulation_detail_view,
    document_simulations_view,
    translate_document_view,
    get_document_translation_view,
    list_document_translations_view,
    translate_analysis_view,
    get_analysis_translation_view,
    list_analysis_translations_view,
    translate_simulation_view,
    get_simulation_translation_view,
    list_simulation_translations_view,
    chat_gemini_view,
)

urlpatterns = [
    path('parse-pdf/', parse_pdf_view, name='parse_pdf'),
    path('documents/', list_parsed_docs_view, name='parsed_docs_list'),
    path('documents/<int:pk>/', parsed_doc_detail_view, name='parsed_doc_detail'),
    path('documents/<int:pk>/analysis/', parsed_doc_analysis_view, name='parsed_doc_analysis'),
    path('documents/<int:pk>/analyze/', parsed_doc_analyze_view, name='parsed_doc_analyze'),
    path('documents/<int:pk>/simulate/', parsed_doc_simulate_view, name='parsed_doc_simulate'),
    path('documents/<int:pk>/simulations/', document_simulations_view, name='document_simulations'),
    path('simulations/import/', import_simulation_view, name='import_simulation'),
    path('simulations/<int:pk>/', simulation_detail_view, name='simulation_detail'),
    # Translation endpoints
    path('documents/<int:pk>/translate/', translate_document_view, name='translate_document'),
    path('documents/<int:pk>/translations/', list_document_translations_view, name='list_document_translations'),
    path('documents/<int:pk>/translations/<str:language>/', get_document_translation_view, name='get_document_translation'),
    # Analysis translation endpoints
    path('analysis/<int:pk>/translate/', translate_analysis_view, name='translate_analysis'),
    path('analysis/<int:pk>/translations/', list_analysis_translations_view, name='list_analysis_translations'),
    path('analysis/<int:pk>/translations/<str:language>/', get_analysis_translation_view, name='get_analysis_translation'),
    # Simulation translation endpoints
    path('simulations/<int:session_id>/translate/', translate_simulation_view, name='translate_simulation'),
    path('simulations/<int:session_id>/translations/', list_simulation_translations_view, name='list_simulation_translations'),
    path('simulations/<int:session_id>/translations/<str:language>/', get_simulation_translation_view, name='get_simulation_translation'),
    # Chat (Gemini) endpoint
    path('chat/gemini/', chat_gemini_view, name='chat_gemini'),
]


