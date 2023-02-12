from django.contrib import admin
from .models import Payment, Order, OrderedFood


class OrderedFoodInline(admin.TabularInline):
    model = OrderedFood
    readonly_fields = ['order', 'payment', 'user', 'fooditem', 'quantity', 'price', 'amount']
    extra = 0


class OrderedAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'name', 'phone', 'email', 'total', 'payment_method', 'order_placed_to', 'status', 'created_at', 'is_ordered']
    inlines = [OrderedFoodInline]



# Register your models here.
admin.site.register(Payment)
admin.site.register(Order, OrderedAdmin)
admin.site.register(OrderedFood)
