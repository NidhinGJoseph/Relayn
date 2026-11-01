from django.urls import path

from communications.views import ConversationDetail, ConversationList, MessageList

urlpatterns = [
    path("organizations/<uuid:organization_id>/conversations/", ConversationList.as_view()),
    path(
        "organizations/<uuid:organization_id>/conversations/<uuid:conversation_id>/",
        ConversationDetail.as_view(),
    ),
    path(
        "organizations/<uuid:organization_id>/conversations/<uuid:conversation_id>/messages/",
        MessageList.as_view(),
    ),
]
