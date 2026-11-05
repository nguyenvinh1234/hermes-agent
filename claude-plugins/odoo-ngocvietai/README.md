# odoo-ngocvietai — Claude Code plugin for Odoo

Connects Claude Code to the Odoo ERP at **https://odoo.ngocvietai.com** (Odoo 16.0).
Claude can look up and report on customers, sales orders, invoices, CRM leads,
products, stock, projects and more, and (with your confirmation) create and update
records.

*Plugin Claude Code kết nối với Odoo tại odoo.ngocvietai.com: tra cứu khách hàng, đơn
bán, hóa đơn, cơ hội CRM, sản phẩm, tồn kho, dự án… và tạo/cập nhật dữ liệu khi bạn
xác nhận.*

## What's inside

| Path | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest: login form (`userConfig`) and the `odoo` MCP server (`python3 server/odoo_mcp.py`). The server is declared here, not in `.mcp.json`, because this repo's `.gitignore` excludes `.mcp.json` files |
| `server/odoo_mcp.py` | MCP stdio server, **Python standard library only**: nothing to `pip install` |
| `skills/odoo/SKILL.md` | Teaches Claude Odoo domains, common models and safe write rules |
| `commands/setup.md` | `/odoo-ngocvietai:setup`: guided configuration and connection check |
| `tests/` | End-to-end test against a fake Odoo JSON-RPC server |

### Tools

`odoo_server_info`, `odoo_list_models`, `odoo_get_fields`, `odoo_search_read`,
`odoo_read`, `odoo_search_count`, `odoo_read_group`: always available, read-only.

`odoo_create`, `odoo_write`, `odoo_call_method`: only when `ODOO_ALLOW_WRITE=1`.
There is no delete tool, `call_method` refuses `unlink`, and every write to an
accounting model (`account.*`) is refused before it reaches Odoo (Ngọc Việt policy:
read-only first, never delete, never edit accounting). Claude Code also asks your
permission before each tool call unless you allow it.

## Install

The plugin lives on branch `claude/happy-fermi-5ksp8h` until it is merged; after the merge
drop the `@claude/happy-fermi-5ksp8h` suffix.

Requirements: Claude Code and `python3` (3.8+) on `PATH`.

```bash
claude plugin marketplace add nguyenvinh1234/hermes-agent@claude/happy-fermi-5ksp8h
```

```bash
claude plugin install odoo-ngocvietai@ngocvietai
```

(or inside Claude Code: `/plugin marketplace add nguyenvinh1234/hermes-agent@claude/happy-fermi-5ksp8h`, then
`/plugin install odoo-ngocvietai@ngocvietai`). For local development:
`claude --plugin-dir ./claude-plugins/odoo-ngocvietai`.

## Log in (Đăng nhập)

1. In Odoo create an API key for the user the AI should act as (prefer a dedicated
   read-only AI user): avatar menu → **Preferences / Tùy chọn** → **Account Security /
   Bảo mật tài khoản** → **New API Key**.
2. In Claude Code open the plugin's login form:

   ```
   /plugin configure odoo-ngocvietai@ngocvietai
   ```

   Fill in **Odoo database** (`odoo`, pre-filled), **Odoo login** and **Odoo API key**.
   The key is a *sensitive* field: Claude Code keeps it in its secure credential storage
   (macOS Keychain; `~/.claude/.credentials.json` elsewhere), not in `settings.json`.
3. Restart Claude Code, then run `/odoo-ngocvietai:setup` to check the login.

Without the form (CI, scripts) set `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY` in the
environment instead; values from the form take precedence. You can also pass them at
install time: `claude plugin install odoo-ngocvietai@ngocvietai --config odoo_username=...`
(avoid putting the key on a command line, where shell history keeps it).

Optional settings (environment variables):

| Variable | Default | Meaning |
|---|---|---|
| `ODOO_URL` | `https://odoo.ngocvietai.com` | Another Odoo instance |
| `ODOO_ALLOW_WRITE` | off | `1` enables create/write/call_method (still no delete, no accounting) |
| `ODOO_TIMEOUT` | `60` | HTTP timeout, seconds |

Keep the API key out of git and chat.

## Examples

- "Liệt kê 10 hóa đơn khách hàng chưa thanh toán, quá hạn nhiều nhất"
- "Doanh thu theo khách hàng tháng 10/2026"
- "Tạo liên hệ mới: Công ty ABC, email abc@example.com"
- "Confirm quotation S00042"

## Test

```bash
python3 -m unittest discover -s claude-plugins/odoo-ngocvietai/tests -v
```

## Notes

- The odoo.ngocvietai.com firewall returns 403 to Python's default
  `Python-urllib` User-Agent, so the server sends `odoo-ngocvietai-mcp/<version>`.
- All calls run as the configured Odoo user; Odoo access rights and record rules apply.
