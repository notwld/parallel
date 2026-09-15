from django.urls import re_path

from apps.chat.consumers import ChannelConsumer

websocket_urlpatterns = [
    re_path(r'^ws/chat/channels/(?P<channel_id>\d+)/$', ChannelConsumer.as_asgi()),
]
