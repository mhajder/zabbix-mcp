TRUTHY_VALUES = ("1", "true", "yes", "on")


def parse_bool(val, default=True):
    """
    Convert a value to boolean.

    A blank or whitespace-only value counts as unset and yields the default,
    so an env var declared without a value (``ZABBIX_VERIFY_SSL=``) cannot
    silently flip a setting off.

    Args:
        val: The value to convert.
        default (bool, optional): The default value to return if val is None or blank. Defaults to True.

    Returns:
        bool: True if val represents a truthy value ("1", "true", "yes", "on"), case-insensitive; otherwise False.
    """
    if val is None:
        return default
    normalized = str(val).strip().casefold()
    if not normalized:
        return default
    return normalized in TRUTHY_VALUES
