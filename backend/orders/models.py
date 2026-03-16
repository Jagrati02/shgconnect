from django.db import models
from django.contrib.auth.models import User
from products.models import Product
# Create your models here.

class Order(models.Model):

    order_status_choices = [
        ('PENDING', 'Pending'), 
        ('CONFIRMED', 'Confirmed'), 
        ('SHIPPED', 'Shipped'), 
        ('DELIVERED', 'Delivered'), 
        ('CANCELLED', 'Cancelled'),
    ]
    payment_status_choices = [
        ('PENDING', 'Pending'), 
        ('COMPLETED', 'Completed'), 
        ('FAILED', 'Failed'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(max_length=20, choices=order_status_choices, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=payment_status_choices, default='PENDING')
    

    def __str__(self):
        return f"Order {self.id} by {self.buyer.username}"
    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.id}"