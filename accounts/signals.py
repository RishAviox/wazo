from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PlayerIDMapping
from .utils import process_gps_file, process_video_file
from games.models import GameGPSData, GameVideoData

# process stats when PlayerID is mapped to wajo user.
@receiver(post_save, sender=PlayerIDMapping, weak=False)
def process_stats(sender, instance, created, **kwargs):
    for gps_instance in GameGPSData.objects.all():
        print(100 * "*")
        print(f"started processing gps file: {gps_instance}")
        process_gps_file(player_id_instance=instance, data_file=gps_instance.data_file)
    
    for stats_instance in GameVideoData.objects.all():
        print(100 * "*")
        print(f"started processing stats video file: {stats_instance}")
        process_video_file(player_id_instance=instance, data_file=stats_instance.data_file)
    
    print(100 * "#")
    print(f"Finished processing user ({instance.user}) with player id ({instance.player_id})")
    print(100 * "#")
    
    
    