from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0005_listing_is_deleted'),
    ]

    operations = [
        # pg_trgm powers the trigram indexes below. Idempotent (CREATE EXTENSION
        # IF NOT EXISTS); requires a role allowed to create extensions.
        TrigramExtension(),
        # Cookbook Section 9: GIN index for keyword containment lookups.
        migrations.AddIndex(
            model_name='listing',
            index=GinIndex(fields=['keywords'], name='idx_listings_keywords'),
        ),
        # Trigram indexes on UPPER(title)/UPPER(description) so the browse/search
        # `icontains` filter (Django emits `UPPER(col) LIKE UPPER(%s)`) is index
        # backed. Written as raw SQL because Django's OpClass generates invalid
        # SQL for a functional-expression GIN index.
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_listings_title_trgm '
                'ON listings_listing USING gin (UPPER(title) gin_trgm_ops);',
            reverse_sql='DROP INDEX IF EXISTS idx_listings_title_trgm;',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX IF NOT EXISTS idx_listings_desc_trgm '
                'ON listings_listing USING gin (UPPER(description) gin_trgm_ops);',
            reverse_sql='DROP INDEX IF EXISTS idx_listings_desc_trgm;',
        ),
    ]
