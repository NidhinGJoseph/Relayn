from django.urls import path

from core.views import CurrentUser, MemberDetail, MemberList, OrganizationDetail, OrganizationList

urlpatterns = [
    path("users/me/", CurrentUser.as_view()),
    path("organizations/", OrganizationList.as_view()),
    path("organizations/<uuid:organization_id>/", OrganizationDetail.as_view()),
    path("organizations/<uuid:organization_id>/members/", MemberList.as_view()),
    path(
        "organizations/<uuid:organization_id>/members/<uuid:membership_id>/",
        MemberDetail.as_view(),
    ),
]
