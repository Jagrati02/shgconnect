from django.db import models
from users.models import SHGProfile


class Category(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Product(models.Model):
    shg                = models.ForeignKey(SHGProfile, on_delete=models.CASCADE, related_name='products')
    name               = models.CharField(max_length=255)
    category           = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description        = models.TextField()
    price              = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_available = models.IntegerField(default=0)
    image              = models.ImageField(upload_to='product_images/', blank=True, null=True)
    is_active          = models.BooleanField(default=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    # Extended fields
    unit               = models.CharField(max_length=50, blank=True, null=True)
    state              = models.CharField(max_length=100, blank=True, null=True)
    bulk_price         = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_order_qty      = models.IntegerField(blank=True, null=True, default=1)
    lead_time_days     = models.IntegerField(blank=True, null=True)
    cluster_enabled    = models.BooleanField(default=False)
    forecast_enabled   = models.BooleanField(default=False)
    tags               = models.CharField(max_length=255, blank=True, null=True)

    # ── Properties so templates work without changes ──

    @property
    def price_per_unit(self):
        """Templates use product.price_per_unit — maps to price field."""
        return self.price

    @property
    def available_stock(self):
        """Templates use product.available_stock — maps to quantity_available."""
        return self.quantity_available

    @property
    def status(self):
        """Templates use product.status — derived from is_active."""
        return 'published' if self.is_active else 'draft'

    @property
    def tags_as_string(self):
        """edit_product.html uses product.tags_as_string."""
        return self.tags or ''

    def __str__(self):
        return f"{self.name} - {self.shg.shg_name}"

    class Meta:
        ordering = ['-created_at']