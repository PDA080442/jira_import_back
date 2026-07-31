import factory
from factory.django import DjangoModelFactory

from accounts.models import Profile, User
from accounts.services.email_verification import create_verification_token


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password12345")
    is_active = False


class ActiveUserFactory(UserFactory):
    is_active = True


class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    locale = "ru-ru"
    timezone = "UTC"
    notification_preferences = factory.LazyFunction(dict)


def create_verified_user(*, email="verified@example.com", password="password12345"):
    user = UserFactory(email=email)
    user.set_password(password)
    user.save()
    Profile.objects.get_or_create(user=user)
    _, raw_token = create_verification_token(user)
    from accounts.services.email_verification import verify_email

    verify_email(raw_token)
    user.refresh_from_db()
    return user, password
