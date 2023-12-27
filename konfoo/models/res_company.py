from odoo import models, fields

import logging
logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    konfoo_url = fields.Char(string='Konfoo URL')
    konfoo_url_staging = fields.Char(string='Staging Konfoo URL')

    konfoo_client_id = fields.Char(string='Client ID')
    konfoo_client_id_staging = fields.Char(string='Staging Client ID')

    konfoo_sync_host = fields.Char(string='Sync Host')
    konfoo_sync_host_staging = fields.Char(string='Staging Sync Host')

    konfoo_sync_key = fields.Char(string='Sync Key')
    konfoo_sync_key_staging = fields.Char(string='Staging Sync Key')

    konfoo_product_lookup_field = fields.Char(string='Product lookup field', default='default_code')
    konfoo_sync_batch_size = fields.Integer(string='Sync batch size', default=100)
    konfoo_default_uom_id = fields.Many2one(comodel_name='uom.uom', string='Default UOM')
