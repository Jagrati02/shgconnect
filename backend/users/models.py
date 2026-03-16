from django.db import models
from django.contrib.auth.models import User

class SHGProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shg_id = models.CharField(max_length=255, unique=True)
    shg_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    members_count = models.IntegerField()
    product_category = models.CharField(max_length=255)
    production_capacity = models.IntegerField()
    verified = models.BooleanField(default=False)

    def __str__(self):
        return self.shg_name
    
class buyerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255,blank=True, null=True)
    address = models.CharField(max_length=255)

    def __str__(self):
        return self.company_name


# Create your models here.
