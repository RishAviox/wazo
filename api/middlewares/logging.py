
from django.contrib import auth
from django.utils.deprecation import MiddlewareMixin

from ..models import APILog

class DatabaseLogMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not isinstance(request.user, auth.get_user_model()):
            if request.user.is_authenticated:
                APILog.objects.create(
                    user=request.user,
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    request_body='',
                    response_message=response.content.decode('utf-8')
                )
            else:
                APILog.objects.create(
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    request_body='',
                    response_message=response.content.decode('utf-8')
                )

        return response