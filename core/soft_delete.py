from django.db import models
from django.utils import timezone

class WajoManager(models.Manager):
    """Custom Manager to exclude soft-deleted objects."""
    
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """Include all objects (soft-deleted and active)."""
        return super().get_queryset()
    
    def deleted_only(self):
        """Return only soft-deleted objects."""
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    
class WajoModel(models.Model):
    """Abstract model with soft delete functionality."""
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Managers
    objects = WajoManager()  # Default manager
    all_objects = models.Manager()  # Includes all records

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete the object."""
        self.deleted_at = timezone.now()
        self.save()

    def restore(self):
        """Restore a soft-deleted object."""
        self.deleted_at = None
        self.save()

    @property
    def is_deleted(self):
        return self.deleted_at is not None
    