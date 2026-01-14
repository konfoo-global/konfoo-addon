from odoo import models, fields

import logging
logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.template'

    konfoo_session_id = fields.Many2one('konfoo.session', 'Konfoo Session ID', readonly=True)
