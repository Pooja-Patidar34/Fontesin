from django import template

from billing.plan_i18n import (
    localized_plan_best_for,
    localized_plan_features,
    localized_plan_name,
    localized_plan_tagline,
)

register = template.Library()


@register.filter
def localized_plan_name_filter(plan):
    return localized_plan_name(plan)


@register.filter
def localized_plan_tagline_filter(plan):
    return localized_plan_tagline(plan)


@register.filter
def localized_plan_best_for_filter(plan):
    return localized_plan_best_for(plan)


@register.filter
def localized_plan_features_filter(plan):
    return localized_plan_features(plan)
