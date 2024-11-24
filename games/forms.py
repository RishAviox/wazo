from django import forms
from .models import Game

class GameAdminForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = '__all__'

    def clean_teams(self):
        teams = self.cleaned_data.get('teams')
        if len(teams) < 2:
            raise forms.ValidationError("A game should have 2 teams.")
        elif teams and len(teams) > 2:
            raise forms.ValidationError("A game can have a maximum of 2 teams.")
        return teams