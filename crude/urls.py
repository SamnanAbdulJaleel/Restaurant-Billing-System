"""crude URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from restaurant import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('login/', views.login),
    path('index/', views.index, name='index'),
    path('logout/', views.logout, name='logout'),
    path('additem/', views.additem, name='additem'),
    path('showitem/', views.showitem, name='showitem'),
    path('show/', views.show, name='show'),
    path('view-order/<int:id>/', views.view_order, name='view_order'),
    path('edit-order/<int:id>/', views.edit_order, name='edit_order'),
    path('delete/<int:id>/', views.destroy, name='destroy'),
    path('print-bill/<int:order_id>/', views.print_bill, name='print_bill'),
    path('tables/', views.tables, name='tables'),
    path('clear-table/<int:table_number>/', views.clear_table, name='clear_table'),
    path('revenue/', views.revenue, name='revenue'),
    path('revenue/filter/', views.revenue_filter, name='revenue_filter'),
    path('revenue/export/excel/', views.export_revenue_excel, name='export_revenue_excel'),
    path('revenue/send-whatsapp/', views.send_whatsapp_report, name='send_whatsapp_report'),
    path('edititem/<int:id>/', views.edititem, name='edititem'),
    path('deleteitem/<str:dishname>/', views.deleteitem, name='deleteitem'),
]
