"""
Thin Flask-Security-Too adapter that delegates all auth logic to
skatetrax.auth.service.  FST requires a UserDatastore *instance* with
specific methods; this class satisfies that contract while keeping
business logic in skatetrax_core.
"""
from skatetrax.models.t_auth import uAuthTable, Role
from skatetrax.auth import service as auth_service

try:
    from flask_security import UserDatastore
except ImportError:
    UserDatastore = None


class SkatetraxUserDatastore(UserDatastore):

    def __init__(self):
        super().__init__(user_model=uAuthTable, role_model=Role)

    # ---- User ops (required by FST / Flask-Login) ----

    def find_user(self, identifier=None, **kwargs):
        return auth_service.find_user(identifier=identifier, **kwargs)

    def get_user(self, id_or_email):
        return auth_service.get_user(id_or_email)

    def create_user(self, **kwargs):
        return auth_service.create_user(**kwargs)

    def commit(self):
        pass

    # ---- Role ops ----

    def find_role(self, role_name):
        return auth_service.find_role(role_name)

    def create_role(self, **kwargs):
        return auth_service.create_role(**kwargs)

    def add_role_to_user(self, user, role):
        return auth_service.add_role_to_user(user, role)

    def remove_role_from_user(self, user, role):
        return auth_service.remove_role_from_user(user, role)

    def get_user_roles(self, user):
        return auth_service.get_user_roles(user)

    # ---- Invite tokens ----

    def validate_invite_token(self, token_str):
        return auth_service.validate_invite_token(token_str)

    def consume_invite_token(self, token_str):
        return auth_service.consume_invite_token(token_str)

    def create_invite_token(self, created_by=None, max_uses=1, expires_at=None):
        return auth_service.create_invite_token(created_by, max_uses, expires_at)

    # ---- Password ops ----

    def update_password(self, user, new_password):
        return auth_service.update_password(user, new_password)

    def create_reset_token(self, user_id):
        return auth_service.create_reset_token(user_id)

    def validate_reset_token(self, token_str):
        return auth_service.validate_reset_token(token_str)

    def consume_reset_token(self, token_str):
        return auth_service.consume_reset_token(token_str)


# Singleton for app.py and FST initialization
skatetrax_user_datastore = SkatetraxUserDatastore() if UserDatastore else None
