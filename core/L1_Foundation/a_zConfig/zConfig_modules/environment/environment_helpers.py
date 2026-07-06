# zOS/core/L1_Foundation/a_zConfig/zConfig_modules/helpers/environment_helpers.py
"""Helper functions for environment configuration."""

from zOS import Path, Colors, Dict, Any

def create_default_env_config(path: Path, _env_data: Dict[str, Any], verbose: bool = False) -> None:
    """Create default environment config .zolo file from defaults.
    
    Args:
        path: Path to create config file at
        _env_data: Environment data dictionary (unused, for signature compatibility)
        verbose: If True, show creation messages (default: False)
    """
    from .config_environment import LOG_PREFIX, YAML_KEY, KEY_DEPLOYMENT, DEFAULT_DEPLOYMENT, KEY_ROLE, DEFAULT_ROLE
    from zlsp.parser.basic.serializer import dumps as zolo_dumps

    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        defaults = {
            YAML_KEY: {
                KEY_DEPLOYMENT: DEFAULT_DEPLOYMENT,
                KEY_ROLE: DEFAULT_ROLE,
                "datacenter": "local",
                "cluster": "single-node",
                "node_id": "node-001",
                "network": {
                    "host": "127.0.0.1",
                    "port": 56891,
                    "external_host": "localhost",
                    "external_port": 56891,
                },
                "websocket": {
                    "host": "127.0.0.1",
                    "port": 8765,
                    "require_auth": False,
                    "allowed_origins": [],
                    "token": "",
                    "max_connections": 100,
                    "ping_interval": 20,
                    "ping_timeout": 10,
                    "ssl_enabled": False,
                    "ssl_cert": None,
                    "ssl_key": None,
                },
                "security": {
                    "require_auth": True,
                    "allow_anonymous": False,
                    "ssl_enabled": False,
                    "ssl_cert_path": "",
                    "ssl_key_path": "",
                },
                "logging": {
                    "app": {
                        "level": "INFO",
                        "format": "detailed",
                        "file_enabled": True,
                        "file_path": "",
                    },
                    "framework": {
                        "level": "DEBUG",
                        "format": "detailed",
                    },
                },
                "performance": {
                    "max_workers": 4,
                    "cache_size": 1000,
                    "cache_ttl": 3600,
                    "timeout": 30,
                },
                "custom_field_1": "value",
                "custom_field_2": 42,
                "custom_field_3": ["item1", "item2"],
            }
        }

        Path(path).write_text(zolo_dumps(defaults) + '\n', encoding="utf-8")
        if verbose:
            print(f"{Colors.CONFIG}{LOG_PREFIX} Created environment config: {path}{Colors.RESET}")
            print(f"{Colors.CONFIG}{LOG_PREFIX} You can edit this file to customize environment settings{Colors.RESET}")

    except Exception as e:
        if verbose:
            print(f"{Colors.ERROR}{LOG_PREFIX} Failed to create environment config: {e}{Colors.RESET}")
