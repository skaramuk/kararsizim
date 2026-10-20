from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("kayit/", views.signup, name="signup"),
    path("giris/", views.SiteLoginView.as_view(), name="login"),
    path("cikis/", LogoutView.as_view(), name="logout"),
]
