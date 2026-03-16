"""
Pytest fixtures for TraceVision API tests.
Provides reusable test data and authenticated clients.
"""
import pytest
from rest_framework.test import APIClient
from accounts.models import WajoUser
from teams.models import Team
from tracevision.models import (
    TraceSession,
    TraceHighlight,
    TraceClipReel,
    TracePlayer,
)


# ============================================================================
# User Fixtures
# ============================================================================

@pytest.fixture
def team(db):
    """Create a team for testing."""
    return Team.objects.create(
        id="TEAM_A",
        name="Test Team A",
        jersey_color="#FF0000",
    )


@pytest.fixture
def other_team(db):
    """Create another team for testing."""
    return Team.objects.create(
        id="TEAM_B",
        name="Test Team B",
        jersey_color="#0000FF",
    )


@pytest.fixture
def player_user(db, team):
    """Create a player user with team."""
    user = WajoUser.objects.create(
        phone_no="+1234567890",
        name="Test Player",
        role="Player",
        team=team,
        jersey_number=10,
        selected_language="en",
    )
    return user


@pytest.fixture
def coach_user(db, team):
    """Create a coach user assigned to team."""
    user = WajoUser.objects.create(
        phone_no="+1234567891",
        name="Test Coach",
        role="Coach",
        selected_language="en",
    )
    # Assign coach to team
    team.coach.add(user)
    return user


@pytest.fixture
def other_player_user(db, other_team):
    """Create a player from different team."""
    user = WajoUser.objects.create(
        phone_no="+1234567892",
        name="Other Player",
        role="Player",
        team=other_team,
        jersey_number=11,
        selected_language="en",
    )
    return user


@pytest.fixture
def other_coach_user(db, other_team):
    """Create a coach from different team."""
    user = WajoUser.objects.create(
        phone_no="+1234567893",
        name="Other Coach",
        role="Coach",
        selected_language="en",
    )
    # Assign coach to other team
    other_team.coach.add(user)
    return user


# ============================================================================
# Data Fixtures
# ============================================================================

@pytest.fixture
def trace_session(db, team, other_team, player_user):
    """Create a trace session (game)."""
    from datetime import date
    return TraceSession.objects.create(
        user=player_user,
        session_id="test-session-001",
        match_date=date.today(),
        status="completed",
        home_team=team,
        away_team=other_team,
        home_score=2,
        away_score=1,
        final_score="2-1",
        video_url="https://example.com/video.mp4",
        age_group="U18",
    )


@pytest.fixture
def trace_player(db, player_user, team, trace_session):
    """Create a trace player linked to user."""
    player = TracePlayer.objects.create(
        name=player_user.name,
        jersey_number=player_user.jersey_number,
        team=team,
        object_id="1",
        position="ST",
        user=player_user,
    )
    # Link player to session via ManyToMany
    player.sessions.add(trace_session)
    return player


@pytest.fixture
def trace_highlight(db, trace_session, trace_player):
    """Create a trace highlight."""
    return TraceHighlight.objects.create(
        session=trace_session,
        highlight_id="highlight-001",
        video_id=1,
        start_offset=120000,
        duration=10000,
        video_stream="https://example.com/video.mp4",
        event_type="goal",
        match_time="19:00",
        half=1,
        player=trace_player,
    )


@pytest.fixture
def trace_clip_reel(db, trace_highlight, trace_player):
    """Create a trace clip reel."""
    return TraceClipReel.objects.create(
        highlight=trace_highlight,
        session=trace_highlight.session,
        event_id="event-001",
        event_type="goal",
        side="home",
        start_ms=120000,
        duration_ms=10000,
        video_type="original",
        generation_status="completed",
        primary_player=trace_player,
    )


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """Create an API client."""
    return APIClient()


@pytest.fixture
def authenticated_player(api_client, player_user):
    """API client authenticated as player."""
    api_client.force_authenticate(user=player_user)
    return api_client


@pytest.fixture
def authenticated_coach(api_client, coach_user):
    """API client authenticated as coach."""
    api_client.force_authenticate(user=coach_user)
    return api_client


@pytest.fixture
def authenticated_other_player(api_client, other_player_user):
    """API client authenticated as other player."""
    api_client.force_authenticate(user=other_player_user)
    return api_client


@pytest.fixture
def authenticated_other_coach(api_client, other_coach_user):
    """API client authenticated as other coach."""
    api_client.force_authenticate(user=other_coach_user)
    return api_client
