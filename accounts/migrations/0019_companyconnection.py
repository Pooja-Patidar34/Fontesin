import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_savedfilter'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyConnection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                ('message', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='connection_requests', to='accounts.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_connections', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', '-created_at'], name='accounts_co_user_id_b1f4d2_idx')],
                'unique_together': {('user', 'company')},
            },
        ),
    ]
