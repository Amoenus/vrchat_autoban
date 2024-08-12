from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="VRCHATBAN",
    settings_files=["settings.toml", ".secrets.toml"],
)
