"""
One-shot data repair for CommercialPlan.features.

The membership template expects each feature to be a dict shaped like
    {"included": bool, "text": str}

Some plans on production have features stored as:
  - plain strings: "Free company creation"
  - Python repr() of dicts: "{'text': 'Free company creation', 'included': True}"

This command rewrites both shapes into the canonical dict form so the
membership page renders correctly without any template hacks.

Usage:
    python manage.py fix_plan_features            # repair in place
    python manage.py fix_plan_features --dry-run  # show what would change
"""

import ast

from django.core.management.base import BaseCommand

from billing.models import CommercialPlan


class Command(BaseCommand):
    help = "Normalize CommercialPlan.features into [{included, text}, ...]."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the proposed changes without saving.",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        changed_plans = 0

        for plan in CommercialPlan.objects.all():
            new_features = []
            mutated = False

            for feat in plan.features or []:
                normalized = _normalize_feature(feat)
                if normalized is None:
                    # unparseable — keep original to avoid data loss
                    normalized = {"included": True, "text": str(feat)}
                if normalized != feat:
                    mutated = True
                new_features.append(normalized)

            if not mutated:
                continue

            changed_plans += 1
            self.stdout.write(self.style.WARNING(f"Plan {plan.code!r}:"))
            for before, after in zip(plan.features, new_features):
                self.stdout.write(f"  {before!r}")
                self.stdout.write(f"    → {after!r}")

            if not dry_run:
                plan.features = new_features
                plan.save(update_fields=["features"])

        if changed_plans == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to repair — all features already in canonical shape."))
        elif dry_run:
            self.stdout.write(self.style.NOTICE(f"\nDry-run: would update {changed_plans} plan(s). Re-run without --dry-run to apply."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nRepaired {changed_plans} plan(s)."))


def _normalize_feature(feat):
    """Return a canonical {included, text} dict, or None if unparseable."""
    # Already canonical.
    if isinstance(feat, dict) and "text" in feat:
        return {
            "included": bool(feat.get("included", True)),
            "text": str(feat.get("text", "")),
        }

    # Plain string — could be a label or a Python-repr of a dict.
    if isinstance(feat, str):
        stripped = feat.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                parsed = None
            if isinstance(parsed, dict) and "text" in parsed:
                return {
                    "included": bool(parsed.get("included", True)),
                    "text": str(parsed.get("text", "")),
                }
        # Not a dict-string; treat the raw string as the label.
        return {"included": True, "text": stripped}

    return None
