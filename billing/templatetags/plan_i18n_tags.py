from django import template

from billing.plan_i18n import (
    deactivated_plan_message,
    localized_plan_best_for,
    localized_plan_features,
    localized_plan_name,
    localized_plan_tagline,
    localized_subscription_status,
    pending_upgrade_access_note,
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


@register.filter
def localized_subscription_status_filter(subscription):
    return localized_subscription_status(subscription)


@register.filter
def pending_upgrade_access_note_filter(plan):
    return pending_upgrade_access_note(localized_plan_name(plan))


@register.filter
def deactivated_plan_message_filter(plan):
    return deactivated_plan_message(localized_plan_name(plan))
