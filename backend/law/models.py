from django.db import models


class SearchLog(models.Model):
    """Logs each law search request proxied through ARR backend."""

    query = models.CharField(max_length=500)
    domain_id = models.CharField(max_length=100, blank=True, default='')
    limit = models.IntegerField(default=10)
    result_count = models.IntegerField(default=0)
    response_time_ms = models.FloatField(default=0)
    source = models.CharField(
        max_length=20,
        default='proxy',
        help_text='proxy | mcp | frontend',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['query']),
        ]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.query} ({self.result_count} results)"
