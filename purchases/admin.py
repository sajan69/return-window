from django.contrib import admin

from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("item_name", "store_name", "owner", "return_by", "status")
    list_filter = ("status", "return_by")
    search_fields = ("item_name", "store_name")
