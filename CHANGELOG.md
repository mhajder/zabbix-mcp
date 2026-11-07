# Changelog

## [0.8.0](https://github.com/mhajder/zabbix-mcp/compare/v0.7.1...v0.8.0) (2026-11-07)


### 🚀 Features

* **problems:** add select_hosts to problem_get ([c87d833](https://github.com/mhajder/zabbix-mcp/commit/c87d8332c15f940b810d1e2bfbabebe914126fc8))


### 🐛 Bug Fixes

* **server:** treat a blank LOG_LEVEL as unset ([20ec024](https://github.com/mhajder/zabbix-mcp/commit/20ec02497a0b6f61d81ebfb551effcf065b33ded))


### 📚 Documentation

* match the README to the code ([ae5ae25](https://github.com/mhajder/zabbix-mcp/commit/ae5ae25d74edb0ca2d1a6c393dc90f333c245c01))


### 🧩 CI

* pin actions to commit SHAs at latest versions ([146e3b5](https://github.com/mhajder/zabbix-mcp/commit/146e3b582ed37f2f8f394856c617dcfc8f6f65ea))
* release with release-please ([0859da3](https://github.com/mhajder/zabbix-mcp/commit/0859da314f45a572e2105ab9af5c21b5a8bf3d62))
* replace softprops/action-gh-release with the gh CLI ([620e1e8](https://github.com/mhajder/zabbix-mcp/commit/620e1e8e7c90e3c05860b173971063f00d4caf25))


### 📦 Build

* **deps:** bump ty to 0.0.98 and type check for all platforms ([7181924](https://github.com/mhajder/zabbix-mcp/commit/7181924a2df61becf3c352d7c930fb2889e8d18c))
* **deps:** raise minimum versions of dev tools and vulnerable dependencies ([07afc2a](https://github.com/mhajder/zabbix-mcp/commit/07afc2a04cbdcca1b6815fef9ded61c54b440e88))
* **deps:** stop Dependabot proposing Python pre-release and minor bumps ([09afeb1](https://github.com/mhajder/zabbix-mcp/commit/09afeb1eaf3ba38c644e8ab0cf915d7f90ebbcab))
* **docker:** pin base images by version and digest and update them with Dependabot ([c2cf619](https://github.com/mhajder/zabbix-mcp/commit/c2cf619e2fd0c6f88bd0d817d601fd0a5c2d2003))
* install optional extras for ty check in pre-commit hook ([a7ea3b5](https://github.com/mhajder/zabbix-mcp/commit/a7ea3b5a366e63116889c68fcb288c93d238cf18))


### 🧪 Tests

* raise line coverage to 99.9% ([5fd4115](https://github.com/mhajder/zabbix-mcp/commit/5fd4115b95cba67296cb172fd7e66d5e00bac62d))

## v0.7.1 (2026-10-23)

### Fix

- **deps**: update certifi to 2026.10.19

## v0.7.0 (2026-10-19)

### Feat

- **items**: find web scenario items
- **hosts**: change templates and proxy in host_update
- **transport**: accept streamable-http as an alias for http
- add Python 3.15 support
- **health**: serve /health and probe it from the Docker healthcheck
- **docker**: drop the MCPO image

### Fix

- **macros**: page usermacro_get in a stable order
- **maintenance**: keep one-off periods in step with the window
- **tools**: mark script_execute and configuration_import destructive
- **tools**: let an empty id list match nothing in *_get tools
- **config**: refuse ZABBIX_TOKEN together with a user or password
- **retry**: retry writes only on 429 and reads on 429/5xx
- **transport**: stop on an unknown MCP_TRANSPORT instead of running stdio
- **sentry**: send no PII unless SENTRY_SEND_DEFAULT_PII asks for it
- **transport**: ignore surrounding spaces in MCP_TRANSPORT
- **transport**: bind loopback when MCP_HTTP_HOST is blank
- **config**: validate settings of enabled features only
- **config**: treat blank env values as unset
- **config**: reject unrecognized boolean settings
- **sentry**: log the enabled message by initialising after logging
- **docker**: run as numeric UID 10001 with root-owned app files

### Refactor

- **server**: read config attributes directly

### Perf

- **client**: share one Zabbix connection across tool calls

## v0.6.1 (2026-09-02)

## v0.6.0 (2026-08-22)

### Feat

- **client**: retry transient Zabbix API failures
- **items**: expose interfaceid on item_create
- **hosts**: add working offset pagination to host_get

### Fix

- **users**: set a role when creating a user
- **problems**: set the add-message flag when a message is given
- **tools**: reject empty id lists before they reach Zabbix
- **history**: detect the item value type instead of defaulting to float
- **server**: require an explicit scheme on ZABBIX_URL
- **users**: replace the removed user type with roleid
- **configuration**: require ids for configuration_export
- **hosts**: validate host and groups before calling host.create
- **maintenance**: always send the required timeperiods
- **configuration**: send the required rules to configuration.import
- **pagination**: keep paging working when output omits the id field
- **tools**: raise ToolError instead of returning an error dict
- **tools**: use selectHostGroups and selectTemplateGroups
- **tools**: route all _get tools through fetch_page/fetch_total
- **history**: drop sortfield/sortorder from trend_get
- **tools**: drop unsupported offset parameter from all _get tools
- **problems**: default event_acknowledge action to acknowledge, not close
- **configuration**: call configuration.import via import_ attribute
- **server**: resolve LOG_LEVEL case-insensitively
- **config**: treat blank env vars as unset

### Perf

- **client**: resolve the Zabbix API version once, off the event loop

## v0.5.3 (2026-07-14)

### Fix

- **tools**: handle string values for severities in problem_get

### Refactor

- **tools**: split zabbix_tools.py into modular sub-modules

## v0.5.2 (2026-07-06)

### Refactor

- update default HTTP bind address and improve transport validation

## v0.5.1 (2026-07-06)

### Fix

- **server**: configure FastMCP to disable banner and update checks
- **docker**: update base image from alpine3.23 to alpine3.24

## v0.5.0 (2026-06-05)

### Feat

- **tools**: enhance export functionality to support YAML format and improve documentation
- **tools**: add simplified search and filter shortcuts to GET tools
- **tools**: add comprehensive pagination support to all _get tools

### Refactor

- **tools**: remove unused parameters from tools
- **tools**: remove example responses from API documentation

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
