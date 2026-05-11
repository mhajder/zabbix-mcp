## v0.4.0 (2026-05-11)

### Feat

- **tools**: support bulk host creation with custom params
- **tools**: support list type for output parameter
- **tools**: add sortfield and sortorder parameters to API tools
- **tools**: add count-only output option to all API tools
- **tools**: add select_* and filter parameters for relational data optimization
- **tools**: add host resolution and problem state filters (#24)

## v0.3.2 (2026-05-09)

### Fix

- update release version distribution name in init_sentry function

## v0.3.1 (2026-05-03)

### Fix

- improve search description in host_get tool

## v0.3.0 (2026-04-09)

### Feat

- add optional tool search transform support

### Fix

- **middleware**: remove deprecated Component.disable() calls for FastMCP 3.0 compatibility (#11)

### Refactor

- replace tag middleware with component visibility

## v0.2.1 (2026-02-19)

### Fix

- update healthcheck command to use nc for service availability

### Refactor

- **zabbix**: improve API session isolation per task

## v0.2.0 (2026-01-25)

### Feat

- add MCP Registry integration and metadata
- add Python 3.14 support

## v0.1.0 (2026-01-06)

### Feat

- add zabbix-mcp server
