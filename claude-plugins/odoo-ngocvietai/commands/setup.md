---
description: Log in to Odoo at odoo.ngocvietai.com and test the connection
---

Help the user log this plugin in to Odoo at https://odoo.ngocvietai.com, then verify it.
Answer in the user's language (Vietnamese if they wrote in Vietnamese).

1. Call the `odoo_server_info` tool.
   - If it succeeds, report the server version, database and logged-in user, and stop.
2. If it reports "Not logged in", a missing database or failed authentication, tell the user to
   open the plugin's login form by typing this in Claude Code:

   ```
   /plugin configure odoo-ngocvietai@ngocvietai
   ```

   and fill in:
   - **Odoo database**: `odoo` for the live Odoo 16 (already the default).
   - **Odoo login**: login email of the Odoo user the AI should act as. Recommend a dedicated
     AI user with read-only rights (e.g. Sales/CRM user), not an administrator.
   - **Odoo API key**: in Odoo open the avatar menu → *Preferences* (Tùy chọn) →
     *Account Security* (Bảo mật tài khoản) → *New API Key*, name it, copy it (shown only once).
     The form stores it in Claude Code's secure credential storage (Keychain on macOS).

   Then restart Claude Code (or run `/mcp` and reconnect the `odoo` server) and run
   `/odoo-ngocvietai:setup` again.
3. Alternatives, only if the form is not available (CI, scripts): environment variables
   `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY` set before starting Claude Code. Values filled in
   the form take precedence over these.

The plugin is **read-only by default**. Only mention `ODOO_ALLOW_WRITE=1` if the user says the
boss approved writing; deleting and accounting changes stay blocked even then.

Never ask the user to paste the API key into the chat, and never write it into a file in the
repository.
