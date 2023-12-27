from odoo import models, fields

import logging
logger = logging.getLogger(__name__)


class KonfooSession(models.Model):
    _name = 'konfoo.session'
    _description = 'Konfoo Session'

    konfoo_session_id = fields.Char('Konfoo Session ID')
    konfoo_object = fields.Text(string='Konfoo Object (JSON)')
    konfoo_bom = fields.Text(string='Konfoo BOM (JSON)')
