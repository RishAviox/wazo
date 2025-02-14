import logging
import pytz
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from core.llm_provider import generate_llm_response
from django.utils import timezone

from cards.models import GreetingCache, InsightCache
from cards.utils import get_status_card_metrics, get_daily_snapshot, get_prompt_for_insight


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the task to update the 'text' field
def update_greeting_text():
    try:
        # Get all greeting cache records
        greeting_cache_records = GreetingCache.objects.all()

        today = datetime.today()
        
        for record in greeting_cache_records:
            if record.user.selected_language == 'he':
                language = "Hebrew"
            else:
                language = "English"
            
            user_data = {
                "name": record.user.name,
                "wellness": get_status_card_metrics(record.user),
                "calendar": get_daily_snapshot(record.user, today),
                "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            israel_tz = pytz.timezone('Asia/Jerusalem')
            utc_time = datetime.now(timezone.utc)
            israel_local_time = utc_time.astimezone(israel_tz)

            prompt = f"""Generate a two-liner greeting only in {language} language for the user with the following data. 
                        Keep the word count around 60 words and make it crisp and to the point for a athelete. Do not include JSON data. 
                        From the data passed, see what should be his main focus for the day.: {user_data}. 
                        {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}
                        Current Date and time: {israel_local_time}
                    """

            greeting = generate_llm_response(prompt)
            # Here, you can define how the `text` is updated
            record.text = greeting
            record.save()

        logger.info("Successfully updated all greeting cache records.")
    except Exception as e:
        logger.error(f"Error updating greeting cache records: {e}")


def update_insight_text():
    try:
        # Query all insights related to the specified card names in one go
        cached_insights = InsightCache.objects.all()

        for cached_insight in cached_insights:
            # Collect updates for bulk saving
            updated_insights = []

            prompt = get_prompt_for_insight(cached_insight.user, cached_insight.card)
            if prompt:
                insight = generate_llm_response(prompt)
                cached_insight.text = insight  # Update the cached insight text
                cached_insight.updated_on = timezone.now()
                updated_insights.append(cached_insight)  # Collect it for bulk save

            # Perform bulk update in one go
            if updated_insights:
                InsightCache.objects.bulk_update(updated_insights, ['text', 'updated_on'])

        logger.info("Successfully updated all greeting cache records.")
    except Exception as e:
        logger.error(f"Error updating Insight cache records: {e}")


# Set up the scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()

    # Add the update_greeting_text job to run every 4 hours
    scheduler.add_job(update_greeting_text, 'interval', hours=4)

    # Add the update_insight_text job to run every 4 hours
    scheduler.add_job(update_insight_text, 'interval', hours=4)

    # Optionally, you can handle job execution and errors
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    scheduler.start()

def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed")
    else:
        logger.info(f"Job {event.job_id} executed successfully")
