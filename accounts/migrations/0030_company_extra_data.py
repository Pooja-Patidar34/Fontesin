from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_company_name_globally_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='extra_data',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
