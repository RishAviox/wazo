# Custom JWT authentication using PyJWT

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from ..models import WajoUser


class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_data = authentication.get_authorization_header(request)
        if not auth_data:
            return None
        
        prefix, token = auth_data.decode('utf-8').split()
        if prefix.lower() != 'bearer':
            return None
        
        return self.authenticate_credentials(token)
    
    def authenticate_credentials(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload['token_type'] != 'access':
                raise exceptions.AuthenticationFailed('Invalid token type, expected access token')

            user = WajoUser.objects.get(phone_no=payload['id'])
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
    
