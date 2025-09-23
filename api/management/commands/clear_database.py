from django.core.management.base import BaseCommand
from django.db import transaction
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


class Command(BaseCommand):
    help = 'Clear all data from database tables while preserving table structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt and clear data immediately',
        )
        parser.add_argument(
            '--tables',
            nargs='+',
            choices=[
                'all',
                'parsed_documents',
                'document_analysis',
                'simulation_sessions',
                'timeline_nodes',
                'penalty_forecasts',
                'exit_comparisons',
                'narrative_outcomes',
                'long_term_points',
                'risk_alerts',
            ],
            default=['all'],
            help='Specify which tables to clear (default: all)',
        )

    def handle(self, *args, **options):
        tables_to_clear = options['tables']
        confirm = options['confirm']

        # Show what will be cleared
        self.stdout.write(self.style.WARNING('🗑️  Database Clear Operation'))
        self.stdout.write('=' * 50)

        if 'all' in tables_to_clear:
            tables_to_clear = [
                'parsed_documents',
                'document_analysis',
                'simulation_sessions',
                'timeline_nodes',
                'penalty_forecasts',
                'exit_comparisons',
                'narrative_outcomes',
                'long_term_points',
                'risk_alerts',
            ]

        # Count records before deletion
        counts = {}
        for table in tables_to_clear:
            if table == 'parsed_documents':
                counts[table] = ParsedDocument.objects.count()
            elif table == 'document_analysis':
                counts[table] = DocumentAnalysis.objects.count()
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

        # Display counts
        total_records = 0
        for table, count in counts.items():
            self.stdout.write(f'📊 {table}: {count} records')
            total_records += count

        self.stdout.write('-' * 50)
        self.stdout.write(f'📈 Total records to delete: {total_records}')
        self.stdout.write('')

        if total_records == 0:
            self.stdout.write(self.style.SUCCESS('✅ Database is already empty!'))
            return

        # Confirmation prompt
        if not confirm:
            self.stdout.write(self.style.ERROR('⚠️  WARNING: This will permanently delete all data!'))
            self.stdout.write('Tables will be preserved, but all rows will be removed.')
            self.stdout.write('')
            
            response = input('Are you sure you want to continue? (yes/no): ').lower().strip()
            if response not in ['yes', 'y']:
                self.stdout.write(self.style.WARNING('❌ Operation cancelled.'))
                return

        # Clear data with transaction
        try:
            with transaction.atomic():
                deleted_counts = {}
                
                # Clear in reverse dependency order to avoid foreign key constraints
                clear_order = [
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
                    if table_name in tables_to_clear:
                        count = model_class.objects.count()
                        if count > 0:
                            model_class.objects.all().delete()
                            deleted_counts[table_name] = count
                            self.stdout.write(f'🗑️  Cleared {table_name}: {count} records')

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('✅ Database cleared successfully!'))
                self.stdout.write('')
                
                # Summary
                total_deleted = sum(deleted_counts.values())
                self.stdout.write('📊 Summary:')
                for table, count in deleted_counts.items():
                    self.stdout.write(f'   • {table}: {count} records deleted')
                self.stdout.write(f'   • Total: {total_deleted} records deleted')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error clearing database: {str(e)}'))
            raise
