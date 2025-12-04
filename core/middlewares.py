# Custom JWT authentication using PyJWT

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from django.contrib import auth
from django.utils.deprecation import MiddlewareMixin

from accounts.models import WajoUser
from accounts.utils import find_user_by_normalized_phone
from .models import APILog


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):             
        auth_data = authentication.get_authorization_header(request)
        if not auth_data:
            return None

        try:
            # Decode and split the authorization header
            auth_parts = auth_data.decode('utf-8').split()
            if len(auth_parts) != 2:
                raise exceptions.AuthenticationFailed('Invalid authorization header format')

            prefix, token = auth_parts
            if prefix.lower() != 'bearer':
                return None

            return self.authenticate_credentials(token)

        except UnicodeDecodeError:
            raise exceptions.AuthenticationFailed('Authorization header must be valid UTF-8')

    def authenticate_credentials(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload['token_type'] != 'access':
                raise exceptions.AuthenticationFailed('Invalid token type, expected access token')

            user = find_user_by_normalized_phone(payload['id'])
            if not user:
                raise exceptions.AuthenticationFailed('No such user')
            return (user, None)

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed('Error decoding token')
        except jwt.ImmatureSignatureError:
            raise exceptions.AuthenticationFailed('Immature token')
        except WajoUser.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')

    def authenticate_header(self, request):
        return 'Bearer'




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