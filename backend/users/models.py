from django.db import models
from django.contrib.auth.models import User


class SHGProfile(models.Model):
    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shgprofile')
    shg_id           = models.CharField(max_length=255, unique=True)
    shg_name         = models.CharField(max_length=255)
    state            = models.CharField(max_length=255)
    phone            = models.CharField(max_length=10, blank=True, null=True)
    location         = models.CharField(max_length=255, blank=True, null=True)
    district         = models.CharField(max_length=255, blank=True, null=True)
    members_count    = models.IntegerField(blank=True, null=True)
    product_category = models.CharField(max_length=255, blank=True, null=True)
    production_capacity = models.IntegerField(blank=True, null=True)
    verified         = models.BooleanField(default=False)

    # Settings fields used in shg_dashboard settings section
    about            = models.TextField(blank=True, null=True)
    reg_no           = models.CharField(max_length=100, blank=True, null=True)
    pin_code         = models.CharField(max_length=6, blank=True, null=True)
    bank_name        = models.CharField(max_length=255, blank=True, null=True)
    account_no       = models.CharField(max_length=50, blank=True, null=True)
    ifsc             = models.CharField(max_length=11, blank=True, null=True)
    upi_id           = models.CharField(max_length=100, blank=True, null=True)
    logo             = models.ImageField(upload_to='shg_logos/', blank=True, null=True)

    # ── property so templates can use shg.name instead of shg.shg_name ──
    @property
    def name(self):
        return self.shg_name

    def __str__(self):
        return self.shg_name


class BuyerProfile(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyerprofile')
    state         = models.CharField(max_length=255, blank=True, null=True)
    phone         = models.CharField(max_length=20, blank=True, null=True)
    company       = models.CharField(max_length=255, blank=True, null=True)
    gst           = models.CharField(max_length=15, blank=True, null=True)
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city          = models.CharField(max_length=100, blank=True, null=True)
    pin_code      = models.CharField(max_length=6, blank=True, null=True)
    avatar        = models.ImageField(upload_to='buyer_avatars/', blank=True, null=True)

    # Notification preferences
    email_orders          = models.BooleanField(default=True)
    email_recommendations = models.BooleanField(default=True)
    price_alerts          = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username