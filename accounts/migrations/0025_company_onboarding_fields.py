from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0024_company_entity_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='house_number',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='district',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='region',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='year_established',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='industry_code',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='keywords',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='employee_count_range',
            field=models.CharField(
                blank=True,
                choices=[
                    ('up_to_10', 'Up to 10'),
                    ('up_to_50', 'Up to 50'),
                    ('up_to_100', 'Up to 100'),
                    ('up_to_1000', 'Up to 1,000'),
                    ('over_1000', 'Over 1,000'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='company',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='logo',
            field=models.FileField(blank=True, null=True, upload_to='company_logos/'),
        ),
    ]
