from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0028_rename_accounts_co_created_idx_imp_accounts_co_created_551a9d_idx'),
    ]

    operations = [
        # Drop the per-tenant uniqueness on (tenant, name). The plain
        # Meta.indexes entry on the same fields is a SEPARATE index created
        # by an earlier migration, so it stays intact.
        migrations.AlterUniqueTogether(
            name='company',
            unique_together=set(),
        ),
        # Global partial unique on Company.name (active rows only). Same
        # pattern as the existing unique_company_registration_id constraint.
        migrations.AddConstraint(
            model_name='company',
            constraint=models.UniqueConstraint(
                fields=['name'],
                condition=Q(is_deleted=False),
                name='unique_company_name_when_active',
            ),
        ),
    ]
