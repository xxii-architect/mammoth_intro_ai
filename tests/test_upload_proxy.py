import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("configure_upload_proxy", Path(__file__).parents[1] / "scripts" / "configure_upload_proxy.py")
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


def test_only_api_location_changes_and_configuration_is_idempotent():
    text = """
server {
    root /var/www/mammothos-ui;
    location / { try_files $uri /index.html; }
    location /api/ {
        client_max_body_size 1m;
        proxy_read_timeout 30s;
        proxy_pass http://127.0.0.1:8000;
    }
}
"""
    configured = proxy.configure(text, 50 * 1024 * 1024)
    assert "client_max_body_size 53477376;" in configured
    assert "proxy_read_timeout 120s;" in configured
    assert configured.count("client_max_body_size") == 1
    assert "location / { try_files $uri /index.html; }" in configured
    assert "proxy_pass http://127.0.0.1:8000;" in configured
    assert proxy.configure(configured, 50 * 1024 * 1024) == configured


def test_site_discovery_is_specific_and_refuses_ambiguity():
    dump = """# configuration file /etc/nginx/sites-enabled/other:
server { root /var/www/other; location /api/ { proxy_pass http://localhost; } }
# configuration file /etc/nginx/sites-enabled/mammoth:
server { root /var/www/mammothos-ui; location /api/ { proxy_pass http://localhost; } }
"""
    assert proxy.find_site(dump, "/var/www/mammothos-ui").name == "mammoth"
    with pytest.raises(ValueError):
        proxy.find_site(dump.replace("/var/www/other", "/var/www/mammothos-ui"), "/var/www/mammothos-ui")


def test_unrecognized_proxy_layout_fails_without_guessing():
    with pytest.raises(ValueError):
        proxy.configure("server { location / { proxy_pass http://localhost; } }", 100)


def test_larger_existing_limits_are_preserved_not_downgraded():
    text = "location /api/ {\n client_max_body_size 100m;\n proxy_read_timeout 10m;\n client_body_timeout 300s;\n proxy_pass http://localhost;\n}"
    configured = proxy.configure(text, 50 * 1024 * 1024)
    assert "client_max_body_size 104857600;" in configured
    assert "proxy_read_timeout 600s;" in configured
    assert "client_body_timeout 300s;" in configured
