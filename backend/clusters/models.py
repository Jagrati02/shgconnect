from django.db import models
from users.models import SHGProfile


class SHGCluster(models.Model):
    """
    Represents one K-Means cluster.
    Created by the import_clusters management command.
    """
    label           = models.IntegerField(unique=True)   # cluster number 0-9
    name            = models.CharField(max_length=100)   # e.g. "Agriculture Cluster"
    primary_livelihood = models.CharField(max_length=100)
    description     = models.TextField(blank=True)

    # ML metrics (stored for dashboard display)
    silhouette_score    = models.FloatField(default=0.5755)
    db_index            = models.FloatField(default=0.3707)
    algorithm           = models.CharField(max_length=50, default='K-Means')
    k_value             = models.IntegerField(default=10)

    # Aggregate stats (computed on import)
    total_shgs          = models.IntegerField(default=0)
    avg_members         = models.FloatField(default=0)
    avg_savings         = models.FloatField(default=0)
    total_capacity      = models.IntegerField(default=0)  # sum of all members

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return f"Cluster {self.label} — {self.name}"

    @property
    def capacity_score(self):
        """Percentage of max possible capacity (max cluster has 29922 SHGs)."""
        return round((self.total_shgs / 29922) * 100, 1)


class SHGClusterMember(models.Model):
    """
    Maps each SHG (by SHG Code from dataset) to its cluster.
    Also stores SHGs that exist in our Django DB via shg_profile FK.
    """
    cluster         = models.ForeignKey(
                        SHGCluster, on_delete=models.CASCADE,
                        related_name='members')
    shg_profile     = models.OneToOneField(
                        SHGProfile, on_delete=models.CASCADE,
                        related_name='cluster_membership',
                        null=True, blank=True)

    # Raw data from cluster_results.csv
    # (used when SHGProfile doesn't exist in DB yet)
    shg_code        = models.CharField(max_length=50)
    shg_name        = models.CharField(max_length=255)
    state           = models.CharField(max_length=100)
    district        = models.CharField(max_length=100)
    block           = models.CharField(max_length=100, blank=True)
    primary_livelihood  = models.CharField(max_length=100)
    secondary_livelihood = models.CharField(max_length=100, blank=True)
    active_members  = models.IntegerField(default=0)
    savings_amount  = models.FloatField(default=0)
    shg_category    = models.CharField(max_length=20, blank=True)
    is_synthetic    = models.BooleanField(default=False)

    joined_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['cluster', 'state', 'district']

    def __str__(self):
        return f"{self.shg_name} → Cluster {self.cluster.label}"
