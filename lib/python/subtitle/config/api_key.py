import configparser
import os


def load_api_key(config_file: str = ".config") -> str:
    """Load API key from env, .env file, or config."""
    if os.environ.get("DEEPSEEK_API"):
        return os.environ["DEEPSEEK_API"]
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]

    search_paths = [
        config_file,
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), ".config"),
        os.path.expanduser("~/.amir/config"),
        os.path.expanduser("~/.env"),
    ]

    for path in search_paths:
        if not os.path.exists(path):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEEPSEEK_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                            return key
                    elif line.startswith("DEEPSEEK_API="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                            return key
        except Exception:
            pass

        try:
            config = configparser.ConfigParser()
            config.read(path)
            if "DEFAULT" in config:
                for key_name in ["DEEPSEEK_API_KEY", "DEEPSEEK_API"]:
                    if key_name in config["DEFAULT"]:
                        key = config["DEFAULT"][key_name].strip()
                        if key and key not in ["REPLACE_WITH_YOUR_KEY", "sk-your-key"]:
                            return key
        except Exception:
            continue

    return ""
