from django.contrib import admin
from restaurant.models import Customer,Dish,Menu,Table
# Register your models here.
admin.site.register(Customer)
admin.site.register(Dish)
admin.site.register(Menu)
admin.site.register(Table)
