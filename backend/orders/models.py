from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from users.models import SHGProfile


class Order(models.Model):

    ORDER_STATUS_CHOICES = [
        ('PENDING',   'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('SHIPPED',   'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('PENDING',   'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED',    'Failed'),
    ]

    buyer          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_as_buyer')
    # shg stores the SHG User (not SHGProfile) — kept consistent with original
    shg            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders_as_shg')
    order_date     = models.DateTimeField(auto_now_add=True)
    total_price    = models.DecimalField(max_digits=10, decimal_places=2)
    order_status   = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES,   default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')

    # ── Properties so templates work without changes ──

    @property
    def status(self):
        """Templates use order.status — maps to order_status in lowercase."""
        return self.order_status.lower()

    @property
    def created_at(self):
        """Templates use order.created_at — maps to order_date."""
        return self.order_date

    @property
    def total_amount(self):
        """Templates use order.total_amount — maps to total_price."""
        return self.total_price

    def __str__(self):
        return f"Order #{self.pk} by {self.buyer.username}"


class OrderItem(models.Model):
    order          = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product        = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity       = models.IntegerField()
    price          = models.DecimalField(max_digits=10, decimal_places=2)
    review_rating  = models.IntegerField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    def get_total(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"