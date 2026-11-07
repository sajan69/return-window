from django.urls import path

from . import views

urlpatterns = [
    path("", views.purchase_list, name="purchase-list"),
    path("purchases/new/", views.purchase_create, name="purchase-create"),
    path("purchases/import/", views.import_preview, name="purchase-import"),
    path("purchases/export.csv", views.export_csv, name="purchase-export-csv"),
    path(
        "purchases/deadlines.ics",
        views.export_calendar,
        name="purchase-export-calendar",
    ),
    path(
        "purchases/import/confirm/",
        views.import_confirm,
        name="purchase-import-confirm",
    ),
    path("purchases/<int:pk>/edit/", views.purchase_update, name="purchase-update"),
    path(
        "purchases/<int:pk>/<str:status>/",
        views.purchase_transition,
        name="purchase-transition",
    ),
]
