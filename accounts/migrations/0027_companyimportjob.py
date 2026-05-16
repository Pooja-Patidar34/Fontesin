import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0026_alter_company_classification'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyImportJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('state', models.CharField(
                    choices=[
                        ('queued', 'Queued'),
                        ('running', 'Running'),
                        ('completed', 'Completed'),
                        ('failed', 'Failed'),
                    ],
                    default='queued',
                    max_length=16,
                )),
                ('filename', models.CharField(max_length=255)),
                ('file_path', models.CharField(max_length=500)),
                ('error_log_path', models.CharField(blank=True, max_length=500, null=True)),
                ('total_rows', models.BigIntegerField(default=0)),
                ('processed_rows', models.BigIntegerField(default=0)),
                ('inserted_rows', models.BigIntegerField(default=0)),
                ('skipped_duplicates', models.BigIntegerField(default=0)),
                ('failed_rows', models.BigIntegerField(default=0)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='company_import_jobs',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('target_tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='company_import_jobs',
                    to='accounts.tenant',
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['created_by', '-created_at'], name='accounts_co_created_idx_imp')],
            },
        ),
    ]
