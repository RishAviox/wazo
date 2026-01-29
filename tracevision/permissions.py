"""
Custom permission classes for TraceClipReel comment system.
Implements least privilege access control for sharing, commenting, and notes.
"""

from rest_framework import permissions
from tracevision.models import TraceClipReelShare


class IsClipReelOwner(permissions.BasePermission):
    """
    Permission to check if user is the owner of the clip reel.
    Owner is determined by primary_player's user relationship.
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReel instance
        if not obj.primary_player:
            return False
        return obj.primary_player.user == request.user


class HasClipReelAccess(permissions.BasePermission):
    """
    Permission to check if user has access to the clip reel.
    Access granted if user is owner OR reel is shared with user (is_active=True).
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReel instance
        user = request.user

        # Owner has access
        if obj.primary_player and obj.primary_player.user == user:
            return True
        
        # Additional check for coaches
        if user.role == "Coach" and obj.primary_player:
            player_user = obj.primary_player.user

            print(f"Coach player user: {player_user}")
            
            # Check if coach is part of the player's team
            if player_user.team:
                team_coaches = player_user.team.coach.all()
                print(f"Team coaches: {team_coaches}::{user}")
                if user in team_coaches:
                    return True
            # Check if coach is part of the player's team
            if player_user.team.id == user.team.id:
                return True
            
            # Check if coach is personally assigned to the player
            if player_user.coach.filter(id=user.id).exists():
                return True

        # Check if shared with can_comment=True
        share = TraceClipReelShare.objects.filter(
            clip_reel=obj, shared_with=user, is_active=True
        ).first()

        if share and share.can_comment:
            return True


        return False


class CanCommentOnClipReel(permissions.BasePermission):
    """
    Permission to check if user can comment on the clip reel.
    
    Rules:
    1. Owner (player) can always comment
    2. Coach can comment if:
       a) The reel is explicitly shared with them (can_comment=True), OR
       b) The coach is part of the player's team, OR
       c) The coach is personally assigned to the player
    3. Other users can comment only if the reel is shared with them (can_comment=True)
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReel instance
        user = request.user

        # Owner can always comment
        if obj.primary_player and obj.primary_player.user == user:
            return True

        # Check if shared with can_comment=True
        share = TraceClipReelShare.objects.filter(
            clip_reel=obj, shared_with=user, is_active=True
        ).first()

        if share and share.can_comment:
            return True

        # Additional check for coaches
        if user.role == "Coach" and obj.primary_player:
            player_user = obj.primary_player.user
            
            # Check if coach is part of the player's team
            if player_user.team:
                team_coaches = player_user.team.coach.all()
                if user in team_coaches:
                    return True
            
            # Check if coach is personally assigned to the player
            if player_user.coach.filter(id=user.id).exists():
                return True

            # Check if coach is part of the player's team
            if player_user.team.id == user.team.id:
                return True

        return False


class IsCommentAuthor(permissions.BasePermission):
    """
    Permission to check if user is the author of the comment.
    Used for edit/delete operations.
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReelComment instance
        return obj.author == request.user


class CanViewComment(permissions.BasePermission):
    """
    Permission to check if user can view a specific comment.
    Uses comment.can_view(user) method for access control.
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReelComment instance
        return obj.can_view(request.user)


class IsNoteAuthor(permissions.BasePermission):
    """
    Permission to check if user is the author of the note.
    Used for edit/delete operations.
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReelNote instance
        return obj.author == request.user


class CanViewNote(permissions.BasePermission):
    """
    Permission to check if user can view a specific note.
    Uses note.can_view(user) method for complex access control.
    """

    def has_object_permission(self, request, view, obj):
        # obj is TraceClipReelNote instance
        return obj.can_view(request.user)


class IsPlayerOrCoach(permissions.BasePermission):
    """
    Permission to check if user is a Player or Coach.
    Required for creating notes.
    """

    def has_permission(self, request, view):
        return request.user.role in ["Player", "Coach"]

