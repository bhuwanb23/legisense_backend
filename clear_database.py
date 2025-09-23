#!/usr/bin/env python
"""
Simple script to clear all data from the database tables.
This script can be run directly without Django management commands.

Usage:
    python clear_database.py [--confirm] [--tables table1 table2 ...]
    
Examples:
    python clear_database.py                    # Interactive mode
    python clear_database.py --confirm          # Skip confirmation
    python clear_database.py --tables simulation_sessions parsed_documents
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'legisense_backend.settings')
django.setup()

from django.db import transaction
from api.models_db.parsed_text import (
    ParsedDocument,
    DocumentAnalysis,
    DocumentTranslation,
    DocumentAnalysisTranslation,
)
from api.models_db.simulation import (
    SimulationSession,
    SimulationTimelineNode,
    SimulationPenaltyForecast,
    SimulationExitComparison,
    SimulationNarrativeOutcome,
    SimulationLongTermPoint,
    SimulationRiskAlert,
    SimulationSessionTranslation,
    SimulationTimelineNodeTranslation,
    SimulationPenaltyForecastTranslation,
    SimulationExitComparisonTranslation,
    SimulationNarrativeOutcomeTranslation,
    SimulationLongTermPointTranslation,
    SimulationRiskAlertTranslation,
)


def clear_database(confirm=False, tables=None):
    """Clear all data from specified database tables."""
    
    if tables is None:
        tables = ['all']
    
    # Show what will be cleared
    print('🗑️  Database Clear Operation')
    print('=' * 50)

    if 'all' in tables:
        tables = [
            'parsed_documents',
            'document_analysis',
            'document_translations',
            'analysis_translations',
            'simulation_sessions',
            'timeline_nodes',
            'penalty_forecasts',
            'exit_comparisons',
            'narrative_outcomes',
            'long_term_points',
            'risk_alerts',
            'simulation_session_translations',
            'timeline_node_translations',
            'penalty_forecast_translations',
            'exit_comparison_translations',
            'narrative_outcome_translations',
            'long_term_point_translations',
            'risk_alert_translations',
        ]

    # Count records before deletion
    counts = {}
    for table in tables:
        if table == 'parsed_documents':
            counts[table] = ParsedDocument.objects.count()
        elif table == 'document_analysis':
            counts[table] = DocumentAnalysis.objects.count()
        elif table == 'document_translations':
            counts[table] = DocumentTranslation.objects.count()
        elif table == 'analysis_translations':
            counts[table] = DocumentAnalysisTranslation.objects.count()
        elif table == 'simulation_sessions':
            counts[table] = SimulationSession.objects.count()
        elif table == 'timeline_nodes':
            counts[table] = SimulationTimelineNode.objects.count()
        elif table == 'penalty_forecasts':
            counts[table] = SimulationPenaltyForecast.objects.count()
        elif table == 'exit_comparisons':
            counts[table] = SimulationExitComparison.objects.count()
        elif table == 'narrative_outcomes':
            counts[table] = SimulationNarrativeOutcome.objects.count()
        elif table == 'long_term_points':
            counts[table] = SimulationLongTermPoint.objects.count()
        elif table == 'risk_alerts':
            counts[table] = SimulationRiskAlert.objects.count()
        elif table == 'simulation_session_translations':
            counts[table] = SimulationSessionTranslation.objects.count()
        elif table == 'timeline_node_translations':
            counts[table] = SimulationTimelineNodeTranslation.objects.count()
        elif table == 'penalty_forecast_translations':
            counts[table] = SimulationPenaltyForecastTranslation.objects.count()
        elif table == 'exit_comparison_translations':
            counts[table] = SimulationExitComparisonTranslation.objects.count()
        elif table == 'narrative_outcome_translations':
            counts[table] = SimulationNarrativeOutcomeTranslation.objects.count()
        elif table == 'long_term_point_translations':
            counts[table] = SimulationLongTermPointTranslation.objects.count()
        elif table == 'risk_alert_translations':
            counts[table] = SimulationRiskAlertTranslation.objects.count()

    # Display counts
    total_records = 0
    for table, count in counts.items():
        print(f'📊 {table}: {count} records')
        total_records += count

    print('-' * 50)
    print(f'📈 Total records to delete: {total_records}')
    print('')

    if total_records == 0:
        print('✅ Database is already empty!')
        return

    # Confirmation prompt
    if not confirm:
        print('⚠️  WARNING: This will permanently delete all data!')
        print('Tables will be preserved, but all rows will be removed.')
        print('')
        
        response = input('Are you sure you want to continue? (yes/no): ').lower().strip()
        if response not in ['yes', 'y']:
            print('❌ Operation cancelled.')
            return

    # Clear data with transaction
    try:
        with transaction.atomic():
            deleted_counts = {}
            
            # Clear in reverse dependency order to avoid foreign key constraints
            clear_order = [
                # Translations first (depend on base tables)
                ('risk_alert_translations', SimulationRiskAlertTranslation),
                ('long_term_point_translations', SimulationLongTermPointTranslation),
                ('narrative_outcome_translations', SimulationNarrativeOutcomeTranslation),
                ('exit_comparison_translations', SimulationExitComparisonTranslation),
                ('penalty_forecast_translations', SimulationPenaltyForecastTranslation),
                ('timeline_node_translations', SimulationTimelineNodeTranslation),
                ('simulation_session_translations', SimulationSessionTranslation),
                ('analysis_translations', DocumentAnalysisTranslation),
                ('document_translations', DocumentTranslation),
                ('risk_alerts', SimulationRiskAlert),
                ('long_term_points', SimulationLongTermPoint),
                ('narrative_outcomes', SimulationNarrativeOutcome),
                ('exit_comparisons', SimulationExitComparison),
                ('penalty_forecasts', SimulationPenaltyForecast),
                ('timeline_nodes', SimulationTimelineNode),
                ('simulation_sessions', SimulationSession),
                ('document_analysis', DocumentAnalysis),
                ('parsed_documents', ParsedDocument),
            ]

            for table_name, model_class in clear_order:
                if table_name in tables:
                    count = model_class.objects.count()
                    if count > 0:
                        model_class.objects.all().delete()
                        deleted_counts[table_name] = count
                        print(f'🗑️  Cleared {table_name}: {count} records')

            print('')
            print('✅ Database cleared successfully!')
            print('')
            
            # Summary
            total_deleted = sum(deleted_counts.values())
            print('📊 Summary:')
            for table, count in deleted_counts.items():
                print(f'   • {table}: {count} records deleted')
            print(f'   • Total: {total_deleted} records deleted')

    except Exception as e:
        print(f'❌ Error clearing database: {str(e)}')
        raise


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Clear all data from database tables')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--tables', nargs='+', 
                       choices=['all', 'parsed_documents', 'document_analysis', 
                               'simulation_sessions', 'timeline_nodes', 'penalty_forecasts',
                               'exit_comparisons', 'narrative_outcomes', 'long_term_points', 'risk_alerts'],
                       default=['all'],
                       help='Specify which tables to clear')
    
    args = parser.parse_args()
    clear_database(confirm=args.confirm, tables=args.tables)
