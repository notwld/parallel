from django.urls import path

from apps.worlds import api as views

urlpatterns = [
    path('<slug:slug>/', views.world_landing, name='world-landing'),
    path('<slug:slug>/join/', views.world_join, name='world-join'),
    path('<slug:slug>/character/', views.my_character, name='world-character'),
]
