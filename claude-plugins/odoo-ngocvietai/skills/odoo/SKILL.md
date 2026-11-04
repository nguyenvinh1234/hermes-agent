---
name: odoo
description: Work with the Odoo ERP at odoo.ngocvietai.com — look up customers/contacts, sales orders, quotations, invoices, payments, CRM leads, products, stock, projects/tasks, employees; build reports and summaries; create or update records. Use whenever the user mentions Odoo, ngocvietai ERP, or asks about business data that lives there (khách hàng, đơn hàng, hóa đơn, sản phẩm, tồn kho, cơ hội CRM, công việc dự án).
---

# Odoo (odoo.ngocvietai.com)

The `odoo` MCP server talks to Odoo **16.0** through its external JSON-RPC API.
Every call runs as the configured user, so Odoo's own access rights and
record rules apply.

## Tools

| Tool | Use for |
|---|---|
| `odoo_server_info` | Check connection, version, DB, current user. Call first if unsure the setup works. |
| `odoo_list_models` | Find a model's technical name (`query: "invoice"` → `account.move`). |
| `odoo_get_fields` | Field names, types, relations and selection values of a model. **Call before building domains or writing values.** |
| `odoo_search_read` | Query records (domain + fields + limit + order). |
| `odoo_read` | Read known IDs. |
| `odoo_search_count` | Count before fetching large sets. |
| `odoo_read_group` | Totals/grouping (revenue per customer, invoices per month). |
| `odoo_create` / `odoo_write` / `odoo_unlink` | Change data — **confirm with the user first**. |
| `odoo_call_method` | Workflow buttons: `action_confirm`, `action_post`, `button_validate`, `name_search`, … |

Write tools are hidden when `ODOO_READ_ONLY=1`.

## Working rules

1. **Always pass `fields`** with only what you need and a small `limit`; omitting
   `fields` returns every non-binary field and burns context.
2. **Count first** (`odoo_search_count`) when a result set might be large, then page
   with `offset`.
3. **Inspect before writing.** Run `odoo_get_fields` on the model, check `required`
   fields and selection values, then show the user the exact values and get a yes
   before `odoo_create` / `odoo_write` / `odoo_unlink` / `odoo_call_method`.
4. **Prefer archiving to deleting:** `odoo_write` with `{"active": false}`.
5. Relational values come back as `[id, "display name"]`. When writing many2one
   use the integer ID; for one2many/many2many use command tuples, e.g.
   `[[6, 0, [ids]]]` (replace), `[[4, id]]` (link), `[[0, 0, {values}]]` (create line).
6. Use `context: {"lang": "vi_VN"}` to get Vietnamese labels if that language is
   installed; `{"active_test": false}` to include archived records.
7. Monetary/aggregate questions → `odoo_read_group` instead of fetching every row.

## Domain syntax

A domain is a list of `[field, operator, value]` triples, AND-ed by default.
Prefix operators: `"|"` (OR of the next two), `"&"`, `"!"`.

```json
[["state", "in", ["sale", "done"]], ["date_order", ">=", "2026-10-01"]]
["|", ["email", "ilike", "@ngocvietai.com"], ["phone", "ilike", "0909"]]
[["partner_id.country_id.code", "=", "VN"]]
```

Operators: `= != > >= < <= like ilike not ilike in not in child_of =? =like =ilike`.
Dates are `"YYYY-MM-DD"`, datetimes `"YYYY-MM-DD HH:MM:SS"` in **UTC**.

## Common models (Odoo 16)

| Business object | Model | Useful fields |
|---|---|---|
| Contacts / customers / vendors | `res.partner` | name, email, phone, is_company, customer_rank, supplier_rank, vat |
| Quotations & sales orders | `sale.order` (+ `sale.order.line`) | name, partner_id, state (draft/sent/sale/done/cancel), date_order, amount_total, user_id |
| Invoices / bills / entries | `account.move` (+ `account.move.line`) | name, move_type (out_invoice/in_invoice/out_refund/…), state, payment_state, invoice_date, invoice_date_due, amount_total, amount_residual |
| Payments | `account.payment` | partner_id, amount, date, payment_type, state |
| CRM leads / opportunities | `crm.lead` | name, partner_id, type (lead/opportunity), stage_id, expected_revenue, probability, user_id |
| Products | `product.product` (variants), `product.template` | name, default_code, list_price, standard_price, qty_available, type |
| Stock transfers | `stock.picking` | name, picking_type_id, state, scheduled_date, partner_id |
| Stock on hand | `stock.quant` | product_id, location_id, quantity |
| Purchases | `purchase.order` | name, partner_id, state, amount_total, date_order |
| Projects / tasks | `project.project`, `project.task` | name, project_id, stage_id, user_ids, date_deadline |
| Employees | `hr.employee` | name, job_id, department_id, work_email |
| Users | `res.users` | name, login |

Installed apps vary — if a model is missing, check with `odoo_list_models`.

## Recipes

- **Unpaid customer invoices:** `account.move` domain
  `[["move_type","=","out_invoice"],["state","=","posted"],["payment_state","in",["not_paid","partial"]]]`,
  fields `name, partner_id, invoice_date_due, amount_residual`, order `invoice_date_due`.
- **Revenue by customer this month:** `odoo_read_group` on `sale.order`, domain
  `[["state","in",["sale","done"]],["date_order",">=","<first day>"]]`, fields
  `["amount_total:sum"]`, groupby `["partner_id"]`, orderby `amount_total desc`.
- **Confirm a quotation:** `odoo_call_method` model `sale.order`, method
  `action_confirm`, args `[[<id>]]` (after the user agrees).
- **Find a partner by name:** `odoo_call_method` model `res.partner`, method
  `name_search`, kwargs `{"name": "Ngọc Việt", "limit": 10}`.

## Troubleshooting

- *Missing credentials / ODOO_DB is not set* → run `/odoo-ngocvietai:setup`.
- *Authentication failed* → wrong login, DB name, or API key (keys are shown only
  once at creation; make a new one under Preferences → Account Security).
- *Access Denied / AccessError* → the Odoo user lacks rights for that model; it is
  not a plugin bug.
