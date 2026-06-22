from django.db import models


class LandAnalysisResult(models.Model):
    """Stores the full regulation analysis result for a land parcel."""

    # Identity
    pnu = models.CharField(max_length=19, blank=True, default='')
    address = models.CharField(max_length=500, blank=True, default='')
    coordinate_x = models.FloatField(null=True, blank=True)
    coordinate_y = models.FloatField(null=True, blank=True)
    zones = models.JSONField(default=list, help_text='List of zone names')
    zone_category = models.CharField(max_length=50, blank=True, default='')

    # Land info
    land_area_m2 = models.FloatField(null=True, blank=True)
    official_land_price = models.IntegerField(null=True, blank=True, help_text='Won/m2')
    land_use_situation = models.CharField(max_length=50, blank=True, default='', help_text='지목')

    # 1. BCR
    bcr_pct = models.FloatField(null=True, blank=True)
    bcr_article = models.CharField(max_length=200, blank=True, default='')

    # 2. FAR
    far_pct = models.FloatField(null=True, blank=True)
    far_article = models.CharField(max_length=200, blank=True, default='')

    # 3. Height limit
    height_limit_m = models.FloatField(null=True, blank=True)
    height_article = models.CharField(max_length=200, blank=True, default='')

    # 4. Sunlight setback
    sunlight_applies = models.BooleanField(default=False)
    sunlight_rules = models.JSONField(default=list)
    sunlight_article = models.CharField(max_length=200, blank=True, default='')

    # 5. Corner cutoff
    corner_cutoff_required = models.BooleanField(default=False)
    corner_cutoff_article = models.CharField(max_length=200, blank=True, default='')

    # 6. Road diagonal
    road_diagonal_multiplier = models.FloatField(null=True, blank=True)
    road_diagonal_rule = models.CharField(max_length=200, blank=True, default='')
    road_diagonal_article = models.CharField(max_length=200, blank=True, default='')

    # 7. Building line
    building_line_setback_m = models.FloatField(null=True, blank=True)
    building_line_article = models.CharField(max_length=200, blank=True, default='')

    # 8. Adjacent setback
    adjacent_setback_m = models.FloatField(null=True, blank=True)
    adjacent_setback_article = models.CharField(max_length=200, blank=True, default='')

    # 9. Parking
    parking_rule = models.CharField(max_length=200, blank=True, default='')
    parking_article = models.CharField(max_length=200, blank=True, default='')

    # 10. Landscaping
    landscaping_threshold_m2 = models.IntegerField(null=True, blank=True)
    landscaping_min_pct = models.FloatField(null=True, blank=True)
    landscaping_article = models.CharField(max_length=200, blank=True, default='')

    # Extended regulations (items 11-41)
    regulations_extended = models.JSONField(
        default=dict, blank=True,
        help_text='Items 11-41: zone/scale/text regulations',
    )

    # Law articles
    law_articles_json = models.JSONField(default=list)
    law_article_count = models.IntegerField(default=0)

    # Data source
    data_source = models.CharField(max_length=50, blank=True, default='static')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['pnu']),
        ]

    def __str__(self):
        zone_str = ', '.join(self.zones[:2]) if self.zones else 'no zones'
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.pnu or self.address or zone_str}"


class LandQuery(models.Model):
    """Audit log for land regulation analysis requests."""

    INPUT_TYPES = [
        ('pnu', 'PNU Code'),
        ('address', 'Address'),
        ('raw', 'Raw Data'),
    ]

    input_type = models.CharField(max_length=10, choices=INPUT_TYPES)
    raw_input = models.CharField(max_length=500)
    resolved_pnu = models.CharField(max_length=19, blank=True, default='')
    resolved_address = models.CharField(max_length=500, blank=True, default='')

    zoning_zones = models.JSONField(default=list, help_text='List of zoning zone names')
    building_coverage_limit = models.FloatField(null=True, blank=True, help_text='BCR %')
    floor_area_limit = models.FloatField(null=True, blank=True, help_text='FAR %')

    land_area_m2 = models.FloatField(null=True, blank=True)
    official_land_price = models.IntegerField(null=True, blank=True, help_text='Won/m2')
    law_article_count = models.IntegerField(default=0)

    analysis_result = models.ForeignKey(
        LandAnalysisResult, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='queries',
    )

    response_time_ms = models.FloatField(default=0)
    source = models.CharField(
        max_length=20,
        default='api',
        help_text='api | mcp | frontend',
    )
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['resolved_pnu']),
        ]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.input_type}:{self.raw_input[:50]}"


class ZoningRegulation(models.Model):
    """Static cache of zoning regulations per zone type."""

    zone_name = models.CharField(max_length=50, unique=True, help_text='e.g. 제1종일반주거지역')
    bcr_default = models.FloatField(help_text='Building Coverage Ratio %')
    far_default = models.FloatField(help_text='Floor Area Ratio %')
    bcr_article = models.CharField(max_length=100, blank=True, default='', help_text='e.g. 제77조')
    far_article = models.CharField(max_length=100, blank=True, default='', help_text='e.g. 제78조')
    restriction_keywords = models.JSONField(default=list, help_text='Keywords for law search')

    class Meta:
        ordering = ['zone_name']

    def __str__(self):
        return f"{self.zone_name} (BCR:{self.bcr_default}% FAR:{self.far_default}%)"
