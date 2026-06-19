from .utils import get_all_drives, get_user_storage_info


def drives_context(request):
    """Inject drives info and user storage info into every template automatically."""
    if not request.user.is_authenticated:
        return {}
    storage = get_user_storage_info(request.user)
    return {
        'drives': get_all_drives(),
        'storage_used_human':  storage['used_h'],
        'storage_total_human': storage['total_h'],
        'storage_pct':         storage['pct'],
        'storage_is_quota':    storage['is_quota'],
    }