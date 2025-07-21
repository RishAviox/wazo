import mimetypes

from django.core.exceptions import ValidationError
from django.db import models


def validate_excel_file(value):
    # Get the file extension
    file_extension = value.name.split('.')[-1].lower()

    # Check if the file is Excel format
    if file_extension not in ['xls', 'xlsx']:
        raise ValidationError('The uploaded file is not a valid Excel file.')

def match_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/match_data/<filename>
    return 'uploads/match_data/{0}'.format(filename)

class ExcelFile(models.Model):
    file = models.FileField(upload_to=match_data_file_path, validators=[validate_excel_file])
    match_id = models.PositiveBigIntegerField(null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
