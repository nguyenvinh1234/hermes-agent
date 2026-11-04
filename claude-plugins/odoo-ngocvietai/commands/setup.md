---
description: Configure and test the connection to Odoo at odoo.ngocvietai.com
---

Help the user connect this plugin to Odoo at https://odoo.ngocvietai.com, then verify it.

1. Call the `odoo_server_info` tool.
   - If it succeeds, report the server version, database and logged-in user, and stop.
2. If it fails with missing credentials, a missing database or failed authentication, explain
   what is needed (answer in the user's language — Vietnamese if they wrote in Vietnamese):
   - **ODOO_DB**: the Odoo database name. It is shown on the login page's database selector, or
     in the URL after `?db=`; ask the Odoo administrator if unsure.
   - **ODOO_USERNAME**: the login email for Odoo.
   - **ODOO_API_KEY**: in Odoo open the avatar menu → *Preferences* (Tùy chọn) →
     *Account Security* (Bảo mật tài khoản) → *New API Key*, give it a name, and copy the key
     (it is shown only once). The account password also works, but an API key is safer and can
     be revoked.
   - The plugin is **read-only by default**. Only set **ODOO_ALLOW_WRITE=1** if the boss has
     approved writing; deleting and accounting changes stay blocked even then.
   - Optional: **ODOO_URL** to point at another Odoo instance.
3. Tell them to set these as environment variables before starting Claude Code, for example
   in `~/.bashrc` / `~/.zshrc`:

   ```bash
   export ODOO_DB="your_database"
   export ODOO_USERNAME="you@example.com"
   export ODOO_API_KEY="paste-key-here"
   ```

   or in Claude Code's `settings.json` under `"env"`. Then restart Claude Code (or run `/mcp`
   to reconnect the `odoo` server) and run `/odoo-ngocvietai:setup` again.

Never ask the user to paste the API key into the chat, and never write it into a file
in the repository.
