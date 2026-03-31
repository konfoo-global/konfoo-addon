from odoo import models, fields, api, _
from datetime import datetime
from pytz import timezone, utc

import json
import logging
logger = logging.getLogger(__name__)


class KonfooSession(models.Model):
    _name = 'konfoo.session'
    _description = 'Konfoo Session'

    konfoo_session_id = fields.Char('Konfoo Session ID')
    konfoo_object = fields.Text(string='Konfoo Object (JSON)')
    konfoo_bom = fields.Text(string='Konfoo BOM (JSON)')
    konfoo_object_html = fields.Html(
        string='Konfoo Configuration',
        compute='_compute_konfoo_object_html',
        sanitize=False,
    )

    @api.depends('konfoo_object')
    def _compute_konfoo_object_html(self):
        for rec in self:
            rec.konfoo_object_html = rec._render_konfoo_html()

    def _render_konfoo_html(self):
        if not self.konfoo_object:
            return ''
        try:
            data = json.loads(self.konfoo_object)
        except (ValueError, TypeError):
            return '<p>Invalid JSON</p>'

        by_id = data.get('by_id', {})
        if not by_id:
            return '<p>No configuration data.</p>'

        created_ts = data.get('created')
        updated_ts = data.get('updated')

        def fmt_ts(ts):
            if not ts:
                return '—'
            user_tz = timezone(self.env.user.tz or 'UTC')
            dt = utc.localize(datetime.utcfromtimestamp(ts)).astimezone(user_tz)
            return dt.strftime('%Y-%m-%d %H:%M')

        root_ref = data.get('root', {}).get('__ref__')

        ordered_ids = []
        if root_ref and root_ref in by_id:
            ordered_ids.append(root_ref)
        for obj_id in by_id:
            if obj_id not in ordered_ids:
                ordered_ids.append(obj_id)

        label_style = (
            'width: 200px; min-width: 200px; padding: 4px 16px 4px 0;'
            'color: #666; font-size: 13px; vertical-align: top;'
        )
        value_style = (
            'padding: 4px 0; font-size: 13px; vertical-align: top;'
        )
        section_style = (
            'font-size: 11px; font-weight: 700; letter-spacing: 0.5px;'
            'text-transform: uppercase; color: #333;'
            'padding: 4px 0; border-bottom: 1px solid #dee2e6;'
            'margin-bottom: 8px;'
        )
        section_wrapper_style = 'margin-top: 24px; margin-bottom: 8px;'

        parts = ['<div style="padding: 0 0 16px 0;">']

        parts.append('<table style="border-collapse: collapse; margin-bottom: 16px;">')
        parts.append(
            f'<tr>'
            f'<td style="{label_style}">{_("Created")}</td>'
            f'<td style="{value_style}">{fmt_ts(created_ts)}</td>'
            f'</tr>'
            f'<tr>'
            f'<td style="{label_style}">{_("Updated")}</td>'
            f'<td style="{value_style}">{fmt_ts(updated_ts)}</td>'
            f'</tr>'
        )
        parts.append('</table>')

        for obj_id in ordered_ids:
            obj = by_id[obj_id]
            obj_fields = obj.get('fields', {})
            obj_name = obj.get('name', '')

            visible_fields = {k: v for k, v in obj_fields.items() if v not in (None, '', [], {})}
            if not visible_fields:
                continue

            title = obj_name if obj_name else obj_id

            parts.append(f'<div style="{section_wrapper_style}"><div style="{section_style}">{title}</div></div>')
            parts.append('<table style="border-collapse: collapse; width: 100%; margin-bottom: 8px;">')
            parts.append(
                f'<tr>'
                f'<td style="{label_style}">{_("ID")}</td>'
                f'<td style="{value_style}">{obj_id}</td>'
                f'</tr>'
            )

            for field_name, field_value in visible_fields.items():
                display_value = (
                    field_value
                    if not isinstance(field_value, (dict, list))
                    else json.dumps(field_value, ensure_ascii=False)
                )
                parts.append(
                    f'<tr>'
                    f'<td style="{label_style}">{field_name}</td>'
                    f'<td style="{value_style}">{display_value}</td>'
                    f'</tr>'
                )

            parts.append('</table>')

        parts.append('</div>')
        return ''.join(parts)
