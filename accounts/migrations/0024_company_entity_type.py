from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0023_grant_company_user_view_to_business_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='entity_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('inc', 'Inc. (Incorporated)'),
                    ('llc', 'LLC (Limited Liability Company)'),
                    ('ltd', 'Ltd. (Limited)'),
                    ('pvt_ltd', 'Pvt. Ltd. (Private Limited)'),
                    ('llp', 'LLP (Limited Liability Partnership)'),
                    ('corp', 'Corp. (Corporation)'),
                    ('gmbh', 'GmbH'),
                    ('ag', 'AG'),
                    ('sa', 'S.A.'),
                    ('sarl', 'S.A.R.L.'),
                    ('bv', 'B.V.'),
                    ('sole_proprietorship', 'Sole Proprietorship'),
                    ('partnership', 'Partnership'),
                    ('non_profit', 'Non-Profit'),
                    ('other', 'Other'),
                ],
                max_length=30,
                null=True,
            ),
        ),
    ]
