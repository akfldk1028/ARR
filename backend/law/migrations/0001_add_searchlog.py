from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SearchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(max_length=500)),
                ('domain_id', models.CharField(blank=True, default='', max_length=100)),
                ('limit', models.IntegerField(default=10)),
                ('result_count', models.IntegerField(default=0)),
                ('response_time_ms', models.FloatField(default=0)),
                ('source', models.CharField(default='proxy', help_text='proxy | mcp | frontend', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['-created_at'], name='law_searchlo_created_idx'),
                    models.Index(fields=['query'], name='law_searchlo_query_idx'),
                ],
            },
        ),
    ]
