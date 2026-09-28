# HMS Web Module (Future)

Placeholder for the optional web frontend. Planned options:

- **Bootstrap + HTML/CSS** — quick admin panels, reports viewer
- **React** — full SPA for remote access and dashboards

## Planned Structure

```
web/
├── public/
├── src/
│   ├── api/          # Backend API client
│   ├── components/
│   ├── modules/      # Mirror backend modules
│   └── pages/
└── package.json
```

The web client will consume the same FastAPI backend at `/api/v1`.
