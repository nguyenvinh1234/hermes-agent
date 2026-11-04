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
| `.claude-plugin/plugin.json` | Plugin manifest |
| `.mcp.json` | Registers the `odoo` MCP server (`python3 server/odoo_mcp.py`) |
| `server/odoo_mcp.py` | MCP stdio server, **Python standard library only**: nothing to `pip install` |
| `skills/odoo/SKILL.md` | Teaches Claude Odoo domains, common models and safe write rules |
| `commands/setup.md` | `/odoo-ngocvietai:setup`: guided configuration and connection check |
| `tests/` | End-to-end test against a fake Odoo JSON-RPC server |

### Tools

`odoo_server_info`, `odoo_list_models`, `odoo_get_fields`, `odoo_search_read`,
`odoo_read`, `odoo_search_count`, `odoo_read_group` (read-only), plus
`odoo_create`, `odoo_write`, `odoo_unlink`, `odoo_call_method` (write; hidden when
`ODOO_READ_ONLY=1`). Claude Code asks your permission before each tool call unless
you allow it.

## Install

Requirements: Claude Code and `python3` (3.8+) on `PATH`.

```bash
claude plugin marketplace add nguyenvinh1234/hermes-agent
```

```bash
claude plugin install odoo-ngocvietai@ngocvietai
```

(or inside Claude Code: `/plugin marketplace add nguyenvinh1234/hermes-agent`, then
`/plugin install odoo-ngocvietai@ngocvietai`). For local development:
`claude --plugin-dir ./claude-plugins/odoo-ngocvietai`.

## Configure

Create an API key in Odoo: avatar menu → **Preferences / Tùy chọn** → **Account
Security / Bảo mật tài khoản** → **New API Key**. Then export, before starting Claude Code:

```bash
export ODOO_DB="your_database"          # database name (the server hides its DB list)
export ODOO_USERNAME="you@example.com"  # Odoo login
export ODOO_API_KEY="..."               # API key (ODOO_PASSWORD also accepted)
```

Optional settings:

| Variable | Default | Meaning |
|---|---|---|
| `ODOO_URL` | `https://odoo.ngocvietai.com` | Another Odoo instance |
| `ODOO_READ_ONLY` | off | `1` hides every tool that modifies data |
| `ODOO_TIMEOUT` | `60` | HTTP timeout, seconds |

You can also put them in `~/.claude/settings.json` under `"env"`. Keep the API key
out of git. Run `/odoo-ngocvietai:setup` to verify.

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
