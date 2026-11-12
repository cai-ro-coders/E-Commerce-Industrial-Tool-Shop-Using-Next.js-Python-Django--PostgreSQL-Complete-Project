from django.utils import timezone


def client_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_activity(user, action, description="", entity_type="", entity_id="", request=None):
    """Write an audit-log entry for important admin actions."""
    from apps.accounts.models import ActivityLog

    return ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        description=description[:2000],
        entity_type=entity_type[:80],
        entity_id=str(entity_id)[:80],
        ip_address=client_ip(request),
    )


def get_setting(key, default=""):
    from apps.core.models import Setting

    item = Setting.objects.filter(key=key).first()
    return item.value if item and item.value not in (None, "") else default


def money(value):
    return float(value or 0)


def day_bounds(day=None):
    day = day or timezone.localdate()
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(
        timezone.datetime.combine(day, timezone.datetime.min.time()), tz
    )
    end = start + timezone.timedelta(days=1)
    return start, end
