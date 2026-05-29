# IT Access — SuperStar demo configuration

This directory is what a tenant config directory looks like. It is the example
SuperStar reads when `SUPERSTAR_CONFIG_DIR` points here (the `.env.example` default).

```
kb-it-access/
├── plugins/
│   └── itaccess.access-request.yaml   # ticket type contract (declarative)
├── kb/
│   ├── vpn-access.md                  # one rule per file, with frontmatter
│   ├── admin-access.md
│   └── prod-data-access.md
├── prompts/
│   └── decisioning.md                 # system prompt for this plugin
└── workflows/
    └── (currently inlined in the plugin YAML)
```

## What the demo decides

Three rules:
- **VPN access** → auto-approve for engineers and contractors.
- **Local admin on company laptop** → auto-approve with one-month expiry note.
- **Production database read access** → always escalate (security-sensitive).

Submit an IT access request, SuperStar matches it to one of these rules,
either auto-decides and cites the rule, or escalates to the configured
approval chain.

## Using this as a template

Copy this directory, rename it, change the plugin identifier and rules. Point
`SUPERSTAR_CONFIG_DIR` at your copy. Do **not** commit your tenant config
into the SuperStar repo — keep it in your own private remote.
