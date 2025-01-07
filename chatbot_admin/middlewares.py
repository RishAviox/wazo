import jwt
from django.conf import settings
from rest_framework import authentication, exceptions
from django.contrib.auth.models import User as DjangoUser


class ChatbotAdminJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_data = authentication.get_authorization_header(request)
        if not auth_data:
            return None
        
        prefix, token = auth_data.decode('utf-8').split()
        if prefix.lower() != 'admin_bearer':
            return None
        
        return self.authenticate_credentials(token)
    
    def authenticate_credentials(self, token):
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload['token_type'] != 'access':
                raise exceptions.AuthenticationFailed('Invalid token type, expected access token')

            user = DjangoUser.objects.get(id=payload['id'])
            print(user)
            return (user, None)
        
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed('Error decoding token')
        except jwt.ImmatureSignatureError:
            raise exceptions.AuthenticationFailed('Immature token')
        except DjangoUser.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')
    
    def authenticate_header(self, request):
        return 'Admin_Bearer'