"""
URL configuration for cfehome project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from auth import views as auth_views
from .views import home_view, about_view

# the way url path work is that they are web paths to the functions present in the views folder. we can tie up the url paths to functions present in the views folder anf then write logic for the page in the views function 
urlpatterns = [
    path("", home_view, name="home"),
    path("login/", auth_views.login_view),
    path("register/", auth_views.register_view),
    path("about/", about_view),
    path("hello-world/", home_view),
    path("hello-world.html",  home_view),
    path('accounts/', include('allauth.urls')),
    path("admin/", admin.site.urls),
]
