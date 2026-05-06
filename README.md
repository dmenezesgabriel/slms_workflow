# Small Language models workflow

```sh
uv run python -m app.download_models
uv run python -m llama_cpp.server --config_file server_config.json
#  in another terminal
uv run python -m app.main
```