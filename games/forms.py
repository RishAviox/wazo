from django import forms
from .models import Game, GameGPSData, GameVideoData


class GameAdminForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = "__all__"

    def clean_teams(self):
        teams = self.cleaned_data.get("teams")
        if len(teams) < 2:
            raise forms.ValidationError("A game should have 2 teams.")
        elif teams and len(teams) > 2:
            raise forms.ValidationError("A game can have a maximum of 2 teams.")
        return teams


class GameGPSDataForm(forms.ModelForm):
    class Meta:
        model = GameGPSData
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "is_processed" in self.fields:
            self.fields["is_processed"].help_text = (
                '<p style="color: red;">Keep it UN-CHECKED if you want the file to be processed automatically.</p>'
            )


class GameVideoDataForm(forms.ModelForm):
    class Meta:
        model = GameVideoData
        fields = [
            "id",
            "data_file",
            "game_type",
            "provider",
            "first_half_url",
            "second_half_url",
            "highlights_url",
            "first_half_padding",
            "second_half_padding",
            "start_time_padding",
            "end_time_padding",
            "is_processed",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "is_processed" in self.fields:
            self.fields["is_processed"].help_text = (
                '<p style="color: red;">Keep it UN-CHECKED if you want the file to be processed automatically.</p>'
            )
