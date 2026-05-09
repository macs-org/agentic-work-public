# Deployment

This folder is Vercel-ready through `api/index.py` and `vercel.json`.

```bash
PATH="$HOME/.nvm/versions/node/v22.22.0/bin:$PATH" vercel --prod --yes
```

For production persistence set `FREIGHT_DB_PATH` to a mounted path or migrate the schema in `app/main.py` to Postgres.
