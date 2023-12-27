from odoo import models, fields, api, _
from .konfoo_api import KonfooContext

import logging
logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_add_konfoo_product(self):
        self.ensure_one()
        ctx = KonfooContext(env=self.env, company_id=self.company_id)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'konfoo.session',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': {
                'default_model': 'konfoo.session',
                'sale_order_id': self.id,
                'konfoo_client_id': ctx.konfoo_client_id,
                'konfoo_url': ctx.konfoo_url,
            },
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    konfoo_session_id = fields.Many2one(
        'konfoo.session',
        compute='_compute_konfoo_session_id', string='Konfoo Session', readonly=True, store=True)

    konfoo_session_key = fields.Char(
        compute='_compute_konfoo_session_id', string='Konfoo Session ID', readonly=True, store=True)

    @api.depends('product_id')
    def _compute_konfoo_session_id(self):
        for line in self:
            session_id = None
            session_key = None
            if line.product_id and line.product_id.konfoo_session_id:
                session_id = line.product_id.konfoo_session_id.id
                session_key = line.product_id.konfoo_session_id.konfoo_session_id
            line.update({
                'konfoo_session_id': session_id,
                'konfoo_session_key': session_key,
            })

    def action_edit_konfoo_product(self):
        self.ensure_one()
        if not self.product_id or not self.product_id.konfoo_session_id:
            return

        konfoo_session_key = self.product_id.konfoo_session_id.konfoo_session_id
        ctx = KonfooContext(env=self.env, company_id=self.company_id)
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'konfoo.session',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': {
                'default_model': 'konfoo.session',
                'sale_order_id': self.order_id.id,
                'konfoo_client_id': ctx.konfoo_client_id,
                'konfoo_url': ctx.konfoo_url,
                'konfoo_session_key': konfoo_session_key,
            },
        }

    def action_duplicate_konfoo_product(self):
        self.ensure_one()
        if not self.product_id or not self.product_id.konfoo_session_id:
            return
        self.env['konfoo.api'].duplicate(self.order_id.id, self.product_id.konfoo_session_id.konfoo_session_id)
