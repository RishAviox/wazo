import os
import json
from django.core.management.base import BaseCommand
from tracevision.tasks import compute_aggregates_task, download_video_and_save_to_azure_blob, parse_excel_match_data, process_excel_match_highlights_task, process_trace_sessions_task
from tracevision.tasks import generate_overlay_highlights_task, update_trace_session_multilingual_data
from tracevision.models import TraceSession


class Command(BaseCommand):
    help = 'Test process_trace_sessions_task'

    def add_arguments(self, parser):
        parser.add_argument('--session-id', type=str, help='Specific session ID')
        parser.add_argument('--all', action='store_true', help='Process all sessions')

    def handle(self, *args, **options):
        if options['session_id']:
            # Test specific session
            # result = process_trace_sessions_task.delay(int(options['session_id']))
            # result = generate_overlay_highlights_task.delay(options['session_id'])
            # result = download_video_and_save_to_azure_blob.delay(options['session_id'])
            # 7a5e1ec970ba40fb87f67398c98a6cb4

            result = process_excel_match_highlights_task.delay(options['session_id'])
            # result = compute_aggregates_task.delay(options['session_id'])
            # result = calculate_card_metrics_task.delay(options['session_id'])
            # result = generate_overlay_highlights_task.delay(int((options['session_id'])))
            # match_data = os.path.join("./tracevision", "data", "Gmae_Match_Detail Template_multilingual.json")
            # with open(match_data, "r", encoding="utf-8") as f:
            #     match_data = json.load(f)
            
            # result = update_trace_session_multilingual_data(match_data, options['session_id'])
             


            # Process the excel file:
            # session = TraceSession.objects.get(session_id=options['session_id'])
            # result = parse_excel_match_data("./HapoelAko_vs_MaccabiHaifa_All-info.xlsx", session)
            
            self.stdout.write(f"Result: {result}")
        elif options['all']:
            # Test all sessions
            sessions = TraceSession.objects.all()
            for session in sessions:
                result = process_trace_sessions_task.delay(session.id)
                self.stdout.write(f"Queued session {session.id}: {result.id}")