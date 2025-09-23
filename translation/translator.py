from typing import List, Dict, Any
import logging
import requests
import json

logger = logging.getLogger(__name__)

class DocumentTranslator:
    """Service for translating document content using Google Translate API."""
    
    def __init__(self):
        # Using Google Translate API via requests
        self.base_url = "https://translate.googleapis.com/translate_a/single"
    
    def translate_text(self, text: str, target_language: str, source_language: str = 'en') -> str:
        """Translate a single text string."""
        try:
            if not text or not text.strip():
                return text
            
            # Use Google Translate API via requests
            params = {
                'client': 'gtx',
                'sl': source_language,
                'tl': target_language,
                'dt': 't',
                'q': text
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result and len(result) > 0 and result[0]:
                translated_text = ''.join([item[0] for item in result[0] if item[0]])
                return translated_text
            
            return text
        except Exception as e:
            logger.error(f"Translation error for text '{text[:50]}...': {e}")
            return text  # Return original text if translation fails
    
    def translate_pages(self, pages: List[Dict[str, Any]], target_language: str, source_language: str = 'en') -> List[Dict[str, Any]]:
        """Translate a list of document pages."""
        translated_pages = []
        
        for page in pages:
            try:
                translated_page = page.copy()
                original_text = page.get('text', '')
                
                if original_text and original_text.strip():
                    translated_text = self.translate_text(original_text, target_language, source_language)
                    translated_page['text'] = translated_text
                
                translated_pages.append(translated_page)
            except Exception as e:
                logger.error(f"Error translating page {page.get('page_number', 'unknown')}: {e}")
                translated_pages.append(page)  # Keep original page if translation fails
        
        return translated_pages
    
    def translate_full_text(self, full_text: str, target_language: str, source_language: str = 'en') -> str:
        """Translate the full document text."""
        return self.translate_text(full_text, target_language, source_language)
    
    def get_language_code(self, language: str) -> str:
        """Convert language name to Google Translate language code."""
        language_map = {
            'en': 'en',
            'english': 'en',
            'hi': 'hi',
            'hindi': 'hi',
            'ta': 'ta',
            'tamil': 'ta',
            'te': 'te',
            'telugu': 'te',
        }
        return language_map.get(language.lower(), 'en')
    
    def translate_analysis_json(self, analysis_json: dict, target_language: str, source_language: str = 'en') -> dict:
        """Translate the entire analysis JSON structure."""
        try:
            translated_analysis = analysis_json.copy()
            
            # Translate TL;DR bullets
            if 'tldr_bullets' in translated_analysis:
                translated_analysis['tldr_bullets'] = [
                    self.translate_text(bullet, target_language, source_language)
                    for bullet in translated_analysis['tldr_bullets']
                ]
            
            # Translate clauses
            if 'clauses' in translated_analysis:
                translated_clauses = []
                for clause in translated_analysis['clauses']:
                    translated_clause = clause.copy()
                    if 'category' in translated_clause:
                        translated_clause['category'] = self.translate_text(
                            translated_clause['category'], target_language, source_language
                        )
                    if 'original_snippet' in translated_clause:
                        translated_clause['original_snippet'] = self.translate_text(
                            translated_clause['original_snippet'], target_language, source_language
                        )
                    if 'explanation' in translated_clause:
                        translated_clause['explanation'] = self.translate_text(
                            translated_clause['explanation'], target_language, source_language
                        )
                    translated_clauses.append(translated_clause)
                translated_analysis['clauses'] = translated_clauses
            
            # Translate risk flags
            if 'risk_flags' in translated_analysis:
                translated_flags = []
                for flag in translated_analysis['risk_flags']:
                    translated_flag = flag.copy()
                    if 'text' in translated_flag:
                        translated_flag['text'] = self.translate_text(
                            translated_flag['text'], target_language, source_language
                        )
                    if 'why' in translated_flag:
                        translated_flag['why'] = self.translate_text(
                            translated_flag['why'], target_language, source_language
                        )
                    translated_flags.append(translated_flag)
                translated_analysis['risk_flags'] = translated_flags
            
            # Translate comparative context
            if 'comparative_context' in translated_analysis:
                translated_context = []
                for context in translated_analysis['comparative_context']:
                    translated_context_item = context.copy()
                    if 'label' in translated_context_item:
                        translated_context_item['label'] = self.translate_text(
                            translated_context_item['label'], target_language, source_language
                        )
                    if 'standard' in translated_context_item:
                        translated_context_item['standard'] = self.translate_text(
                            translated_context_item['standard'], target_language, source_language
                        )
                    if 'contract' in translated_context_item:
                        translated_context_item['contract'] = self.translate_text(
                            translated_context_item['contract'], target_language, source_language
                        )
                    if 'assessment' in translated_context_item:
                        translated_context_item['assessment'] = self.translate_text(
                            translated_context_item['assessment'], target_language, source_language
                        )
                    translated_context.append(translated_context_item)
                translated_analysis['comparative_context'] = translated_context
            
            # Translate suggested questions
            if 'suggested_questions' in translated_analysis:
                translated_analysis['suggested_questions'] = [
                    self.translate_text(question, target_language, source_language)
                    for question in translated_analysis['suggested_questions']
                ]
            
            return translated_analysis
            
        except Exception as e:
            logger.error(f"Error translating analysis JSON: {e}")
            return analysis_json  # Return original if translation fails

    def translate_simulation_session(self, session_data: dict, target_language: str, source_language: str = 'en') -> dict:
        """Translate simulation session data."""
        try:
            translated_session = session_data.copy()
            
            if 'title' in translated_session and translated_session['title']:
                translated_session['title'] = self.translate_text(
                    translated_session['title'], target_language, source_language
                )
            
            if 'jurisdiction' in translated_session and translated_session['jurisdiction']:
                translated_session['jurisdiction'] = self.translate_text(
                    translated_session['jurisdiction'], target_language, source_language
                )
            
            if 'jurisdiction_note' in translated_session and translated_session['jurisdiction_note']:
                translated_session['jurisdiction_note'] = self.translate_text(
                    translated_session['jurisdiction_note'], target_language, source_language
                )
            
            return translated_session
            
        except Exception as e:
            logger.error(f"Error translating simulation session: {e}")
            return session_data

    def translate_timeline_nodes(self, nodes: list, target_language: str, source_language: str = 'en') -> list:
        """Translate timeline nodes data."""
        try:
            translated_nodes = []
            for node in nodes:
                translated_node = node.copy()
                
                if 'title' in translated_node:
                    translated_node['title'] = self.translate_text(
                        translated_node['title'], target_language, source_language
                    )
                
                if 'description' in translated_node:
                    translated_node['description'] = self.translate_text(
                        translated_node['description'], target_language, source_language
                    )
                
                if 'detailed_description' in translated_node:
                    translated_node['detailed_description'] = self.translate_text(
                        translated_node['detailed_description'], target_language, source_language
                    )
                
                if 'risks' in translated_node and isinstance(translated_node['risks'], list):
                    translated_node['risks'] = [
                        self.translate_text(risk, target_language, source_language)
                        for risk in translated_node['risks']
                    ]
                
                translated_nodes.append(translated_node)
            
            return translated_nodes
            
        except Exception as e:
            logger.error(f"Error translating timeline nodes: {e}")
            return nodes

    def translate_penalty_forecasts(self, forecasts: list, target_language: str, source_language: str = 'en') -> list:
        """Translate penalty forecast data."""
        try:
            translated_forecasts = []
            for forecast in forecasts:
                translated_forecast = forecast.copy()
                
                if 'label' in translated_forecast:
                    translated_forecast['label'] = self.translate_text(
                        translated_forecast['label'], target_language, source_language
                    )
                
                translated_forecasts.append(translated_forecast)
            
            return translated_forecasts
            
        except Exception as e:
            logger.error(f"Error translating penalty forecasts: {e}")
            return forecasts

    def translate_exit_comparisons(self, comparisons: list, target_language: str, source_language: str = 'en') -> list:
        """Translate exit comparison data."""
        try:
            translated_comparisons = []
            for comparison in comparisons:
                translated_comparison = comparison.copy()
                
                if 'label' in translated_comparison:
                    translated_comparison['label'] = self.translate_text(
                        translated_comparison['label'], target_language, source_language
                    )
                
                if 'penalty_text' in translated_comparison:
                    translated_comparison['penalty_text'] = self.translate_text(
                        translated_comparison['penalty_text'], target_language, source_language
                    )
                
                if 'benefits_lost' in translated_comparison:
                    translated_comparison['benefits_lost'] = self.translate_text(
                        translated_comparison['benefits_lost'], target_language, source_language
                    )
                
                translated_comparisons.append(translated_comparison)
            
            return translated_comparisons
            
        except Exception as e:
            logger.error(f"Error translating exit comparisons: {e}")
            return comparisons

    def translate_narrative_outcomes(self, outcomes: list, target_language: str, source_language: str = 'en') -> list:
        """Translate narrative outcomes data."""
        try:
            translated_outcomes = []
            for outcome in outcomes:
                translated_outcome = outcome.copy()
                
                if 'title' in translated_outcome:
                    translated_outcome['title'] = self.translate_text(
                        translated_outcome['title'], target_language, source_language
                    )
                
                if 'subtitle' in translated_outcome:
                    translated_outcome['subtitle'] = self.translate_text(
                        translated_outcome['subtitle'], target_language, source_language
                    )
                
                if 'narrative' in translated_outcome:
                    translated_outcome['narrative'] = self.translate_text(
                        translated_outcome['narrative'], target_language, source_language
                    )
                
                if 'key_points' in translated_outcome and isinstance(translated_outcome['key_points'], list):
                    translated_outcome['key_points'] = [
                        self.translate_text(point, target_language, source_language)
                        for point in translated_outcome['key_points']
                    ]
                
                if 'financial_impact' in translated_outcome and isinstance(translated_outcome['financial_impact'], list):
                    translated_outcome['financial_impact'] = [
                        self.translate_text(impact, target_language, source_language)
                        for impact in translated_outcome['financial_impact']
                    ]
                
                translated_outcomes.append(translated_outcome)
            
            return translated_outcomes
            
        except Exception as e:
            logger.error(f"Error translating narrative outcomes: {e}")
            return outcomes

    def translate_long_term_points(self, points: list, target_language: str, source_language: str = 'en') -> list:
        """Translate long-term forecast points data."""
        try:
            translated_points = []
            for point in points:
                translated_point = point.copy()
                
                if 'label' in translated_point and translated_point['label']:
                    translated_point['label'] = self.translate_text(
                        translated_point['label'], target_language, source_language
                    )
                
                if 'description' in translated_point and translated_point['description']:
                    translated_point['description'] = self.translate_text(
                        translated_point['description'], target_language, source_language
                    )
                
                translated_points.append(translated_point)
            
            return translated_points
            
        except Exception as e:
            logger.error(f"Error translating long-term points: {e}")
            return points

    def translate_risk_alerts(self, alerts: list, target_language: str, source_language: str = 'en') -> list:
        """Translate risk alerts data."""
        try:
            translated_alerts = []
            for alert in alerts:
                translated_alert = alert.copy()
                
                if 'message' in translated_alert:
                    translated_alert['message'] = self.translate_text(
                        translated_alert['message'], target_language, source_language
                    )
                
                translated_alerts.append(translated_alert)
            
            return translated_alerts
            
        except Exception as e:
            logger.error(f"Error translating risk alerts: {e}")
            return alerts

    def translate_simulation_data(self, simulation_data: dict, target_language: str, source_language: str = 'en') -> dict:
        """Translate complete simulation data structure."""
        try:
            translated_data = simulation_data.copy()
            
            # Translate session data
            if 'session' in translated_data:
                translated_data['session'] = self.translate_simulation_session(
                    translated_data['session'], target_language, source_language
                )
            
            # Translate timeline nodes
            if 'timeline' in translated_data:
                translated_data['timeline'] = self.translate_timeline_nodes(
                    translated_data['timeline'], target_language, source_language
                )
            
            # Translate penalty forecasts
            if 'penalty_forecast' in translated_data:
                translated_data['penalty_forecast'] = self.translate_penalty_forecasts(
                    translated_data['penalty_forecast'], target_language, source_language
                )
            
            # Translate exit comparisons
            if 'exit_comparisons' in translated_data:
                translated_data['exit_comparisons'] = self.translate_exit_comparisons(
                    translated_data['exit_comparisons'], target_language, source_language
                )
            
            # Translate narrative outcomes
            if 'narratives' in translated_data:
                translated_data['narratives'] = self.translate_narrative_outcomes(
                    translated_data['narratives'], target_language, source_language
                )
            
            # Translate long-term points
            if 'long_term' in translated_data:
                translated_data['long_term'] = self.translate_long_term_points(
                    translated_data['long_term'], target_language, source_language
                )
            
            # Translate risk alerts
            if 'risk_alerts' in translated_data:
                translated_data['risk_alerts'] = self.translate_risk_alerts(
                    translated_data['risk_alerts'], target_language, source_language
                )
            
            return translated_data
            
        except Exception as e:
            logger.error(f"Error translating simulation data: {e}")
            return simulation_data
