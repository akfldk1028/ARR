from django.contrib import admin

from land.models import LandQuery, LandAnalysisResult, ZoningRegulation


@admin.register(LandAnalysisResult)
class LandAnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['pnu', 'zone_category', 'bcr_pct', 'far_pct',
                    'sunlight_applies', 'road_diagonal_multiplier', 'created_at']
    list_filter = ['zone_category', 'sunlight_applies', 'data_source']
    search_fields = ['pnu', 'address']
    readonly_fields = ['created_at']
    fieldsets = [
        ('Identity', {'fields': ['pnu', 'address', 'coordinate_x', 'coordinate_y',
                                  'zones', 'zone_category']}),
        ('Land Info', {'fields': ['land_area_m2', 'official_land_price']}),
        ('BCR/FAR', {'fields': ['bcr_pct', 'bcr_article', 'far_pct', 'far_article']}),
        ('Height', {'fields': ['height_limit_m', 'height_article']}),
        ('Sunlight', {'fields': ['sunlight_applies', 'sunlight_rules', 'sunlight_article']}),
        ('Corner Cutoff', {'fields': ['corner_cutoff_required', 'corner_cutoff_article']}),
        ('Road Diagonal', {'fields': ['road_diagonal_multiplier', 'road_diagonal_rule',
                                       'road_diagonal_article']}),
        ('Building Line', {'fields': ['building_line_setback_m', 'building_line_article']}),
        ('Adjacent Setback', {'fields': ['adjacent_setback_m', 'adjacent_setback_article']}),
        ('Parking', {'fields': ['parking_rule', 'parking_article']}),
        ('Landscaping', {'fields': ['landscaping_threshold_m2', 'landscaping_min_pct',
                                     'landscaping_article']}),
        ('Extended (11-41)', {'fields': ['regulations_extended'], 'classes': ['collapse']}),
        ('Law Articles', {'fields': ['law_articles_json', 'law_article_count']}),
        ('Meta', {'fields': ['data_source', 'created_at']}),
    ]


@admin.register(LandQuery)
class LandQueryAdmin(admin.ModelAdmin):
    list_display = ['input_type', 'raw_input', 'resolved_pnu', 'building_coverage_limit',
                    'floor_area_limit', 'response_time_ms', 'created_at']
    list_filter = ['input_type', 'source']
    search_fields = ['raw_input', 'resolved_pnu']
    readonly_fields = ['created_at']


@admin.register(ZoningRegulation)
class ZoningRegulationAdmin(admin.ModelAdmin):
    list_display = ['zone_name', 'bcr_default', 'far_default', 'bcr_article', 'far_article']
    search_fields = ['zone_name']
