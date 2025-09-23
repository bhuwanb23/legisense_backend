#!/usr/bin/env python
"""
Quick script to check database status and record counts.
Useful for verifying database state before and after clearing.

Usage:
    python check_database_status.py
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

from api.models_db.parsed_text import ParsedDocument, DocumentAnalysis
from api.models_db.simulation import (
    SimulationSession,
    SimulationTimelineNode,
    SimulationPenaltyForecast,
    SimulationExitComparison,
    SimulationNarrativeOutcome,
    SimulationLongTermPoint,
    SimulationRiskAlert,
)


def check_database_status():
    """Check and display database status."""
    
    print('📊 Database Status Report')
    print('=' * 50)
    
    # Core document tables
    print('📄 Document Tables:')
    print(f'   • ParsedDocument: {ParsedDocument.objects.count()} records')
    print(f'   • DocumentAnalysis: {DocumentAnalysis.objects.count()} records')
    print('')
    
    # Simulation tables
    print('🎯 Simulation Tables:')
    print(f'   • SimulationSession: {SimulationSession.objects.count()} records')
    print(f'   • SimulationTimelineNode: {SimulationTimelineNode.objects.count()} records')
    print(f'   • SimulationPenaltyForecast: {SimulationPenaltyForecast.objects.count()} records')
    print(f'   • SimulationExitComparison: {SimulationExitComparison.objects.count()} records')
    print(f'   • SimulationNarrativeOutcome: {SimulationNarrativeOutcome.objects.count()} records')
    print(f'   • SimulationLongTermPoint: {SimulationLongTermPoint.objects.count()} records')
    print(f'   • SimulationRiskAlert: {SimulationRiskAlert.objects.count()} records')
    print('')
    
    # Calculate totals
    total_documents = ParsedDocument.objects.count() + DocumentAnalysis.objects.count()
    total_simulations = (
        SimulationSession.objects.count() +
        SimulationTimelineNode.objects.count() +
        SimulationPenaltyForecast.objects.count() +
        SimulationExitComparison.objects.count() +
        SimulationNarrativeOutcome.objects.count() +
        SimulationLongTermPoint.objects.count() +
        SimulationRiskAlert.objects.count()
    )
    total_records = total_documents + total_simulations
    
    print('📈 Summary:')
    print(f'   • Document records: {total_documents}')
    print(f'   • Simulation records: {total_simulations}')
    print(f'   • Total records: {total_records}')
    print('')
    
    # Status indicators
    if total_records == 0:
        print('✅ Database is empty')
    elif total_records < 10:
        print('🟡 Database has minimal data')
    elif total_records < 100:
        print('🟢 Database has moderate data')
    else:
        print('🔴 Database has substantial data')
    
    # Recent activity
    if SimulationSession.objects.exists():
        latest_session = SimulationSession.objects.latest('created_at')
        print(f'📅 Latest simulation: {latest_session.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
    
    if ParsedDocument.objects.exists():
        latest_doc = ParsedDocument.objects.latest('created_at')
        print(f'📅 Latest document: {latest_doc.created_at.strftime("%Y-%m-%d %H:%M:%S")}')


if __name__ == '__main__':
    check_database_status()
