from django.contrib.auth import get_user_model


class EmailOrUsernameBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        identifier = username or kwargs.get(UserModel.USERNAME_FIELD) or kwargs.get("email")
        if not identifier or not password:
            return None

        users = UserModel.objects.filter(email__iexact=identifier)
        for candidate in users:
            if candidate.check_password(password) and self.user_can_authenticate(candidate):
                return candidate

        try:
            user = UserModel.objects.get(**{UserModel.USERNAME_FIELD: identifier})
        except UserModel.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", True)

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
