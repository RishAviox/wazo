import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .tasks import auto_map_user_to_player_task

# Configure logger for this module
logger = logging.getLogger()


@receiver(post_save, sender="accounts.WajoUser")
def auto_map_user_to_player_on_create_or_update(sender, instance, created, **kwargs):
    """
    Signal handler triggered when a WajoUser is created or updated.
    If the user has jersey_number and team, automatically map them to matching TracePlayers.

    This runs the auto_map_user_to_player_task in the background.
    """
    try:
        # Skip if phone_no is None (coaches/referees created from Excel don't have phone numbers)
        if not instance.phone_no:
            logger.debug(
                f"User {instance.id} has no phone_no (likely Coach/Referee from Excel). "
                f"Skipping auto-mapping."
            )
            return
        
        # Only proceed if user has both jersey_number and team
        if instance.jersey_number and instance.team:
            logger.info(
                f"User {instance.phone_no} has jersey_number ({instance.jersey_number}) "
                f"and team ({instance.team.id}). Triggering auto-mapping task."
            )
            # Trigger the task asynchronously
            auto_map_user_to_player_task.delay(instance.phone_no)
        else:
            logger.debug(
                f"User {instance.phone_no} does not have jersey_number or team. "
                f"Skipping auto-mapping."
            )
    except Exception as e:
        logger.exception(
            f"Error in auto_map_user_to_player_on_create_or_update for user {instance.phone_no}: {e}"
        )
