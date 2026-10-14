from django.urls import path

from .views import (
    ReminderListCreateView,
    ProcessReminderWorkflowView,
)


urlpatterns = [
    path(
        "",
        ReminderListCreateView.as_view(),
        name="reminder-list-create",
    ),

    path(
        "process/",
        ProcessReminderWorkflowView.as_view(),
        name="process-reminders",
    ),
]
