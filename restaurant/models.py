from django.db import models
from datetime import datetime
from django.db.models.manager import Manager
  

class TableManager(Manager):
    def get_queryset(self):
        return super().get_queryset()

class Table(models.Model):
    number = models.IntegerField(unique=True)
    is_occupied = models.BooleanField(default=False)
    current_order = models.OneToOneField('Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='table')
    
    objects = TableManager()
    
    class Meta:
        db_table = 'restaurant_tables'
        managed = True
        app_label = 'restaurant'
    
    def __str__(self):
        return f"Table {self.number}"

class Customer(models.Model):
    userid = models.CharField(max_length=100)
    time = models.CharField(max_length=100)
    amount = models.IntegerField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_type = models.CharField(max_length=20, choices=[('dine-in', 'Dine In'), ('parcel', 'Parcel')], default='dine-in')
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='pending')
    
    class Meta:  
        db_table = "customer"  
    
    def __str__(self): 
        return f"Order {self.id} - {self.order_type} - {self.status}"

class Dish(models.Model):
    oid = models.IntegerField()
    dname = models.TextField(max_length=122)
    dquantity = models.IntegerField()
    damount = models.IntegerField()
    
    class Meta:  
        db_table = "dish"  
    
    def __str__(self): 
        return self.dname 

class Menu(models.Model):
    userid = models.EmailField(max_length=254)
    dishname = models.TextField(max_length=200)
    dishprice = models.IntegerField()
    dishtype = models.TextField(max_length=200)
    
    class Meta:
        db_table = "menu"
    
    def __str__(self):
        return self.dishname



