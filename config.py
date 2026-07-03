import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 9823,
    "sender_comp_id": "SENDER",
    "target_comp_id": "TARGET",
    "username": "user",
    "password": "password",
    "heartbeat_interval": 30,
    "client_role": "INITIATOR",
    "client_reset_seq": True,
    "server_host": "127.0.0.1",
    "server_port": 9823,
    "server_sender_comp_id": "SERVER",
    "server_target_comp_id": "CLIENT",
    "server_role": "ACCEPTOR",
    "server_reset_seq": True,
    "server_target_host": "127.0.0.1",
    "server_target_port": 9824,
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
