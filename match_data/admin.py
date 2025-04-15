from core.admin import admin_site

from match_data.models.bepro import *
from match_data.models.generic import ExcelFile


admin_site.register(BeproLeagueDetail)
admin_site.register(BeproSeason)
admin_site.register(BeproMatchData)
admin_site.register(BeproMatchDetail)
admin_site.register(BeproEventData)
admin_site.register(BeproFormationData)
admin_site.register(BeproSequenceData)
admin_site.register(BeproPhysicalEventData)
admin_site.register(BeproLineUp)
admin_site.register(BeproPlayerStat)
admin_site.register(BeproPlayerStatsExtended)
admin_site.register(BeproPlayer)
admin_site.register(BeproTeamStat)
admin_site.register(ExcelFile)
admin_site.register(PostMatchAnalysis)
