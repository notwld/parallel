from django.urls import path

from apps.chat import api as views

urlpatterns = [
    path('servers/', views.servers, name='chat-servers'),
    path('servers/<int:server_id>/', views.server_detail, name='chat-server-detail'),
    path('servers/<int:server_id>/channels/', views.server_channels, name='chat-server-channels'),
    path('servers/<int:server_id>/invites/', views.invites_create, name='chat-invites-create'),
    path('servers/<int:server_id>/bans/', views.server_ban, name='chat-server-ban'),
    path('dms/', views.dm_open, name='chat-dm-open'),
    path('group-dms/', views.group_dm_create, name='chat-group-dm'),
    path('invites/join/', views.invites_join, name='chat-invites-join'),
    path('channels/<int:channel_id>/messages/', views.channel_messages, name='chat-messages'),
    path('channels/<int:channel_id>/typing/', views.channel_typing, name='chat-typing'),
    path('channels/<int:channel_id>/read-state/', views.read_state, name='chat-read-state'),
    path('messages/<int:message_id>/', views.message_detail, name='chat-message-detail'),
]
