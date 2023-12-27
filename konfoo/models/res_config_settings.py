from odoo import models, fields, _
from odoo.exceptions import UserError
from urllib.parse import urljoin
from json import JSONDecodeError
import requests
import logging

logger = logging.getLogger(__name__)


def test_konfoo_connection(profile, konfoo_url, client_id, sync_url, sync_key):
    if not konfoo_url:
        raise UserError(_('Konfoo URL not configured'))

    response = requests.get(urljoin(konfoo_url, '/api/v1/state'))
    if not response:
        raise UserError(_('Could not establish connection to Konfoo: %s', str(response)))
    try:
        remote_config = response.json()
    except JSONDecodeError:
        raise UserError(_('Unexpected response from Konfoo: %s', response.text))

    if 'requires_key' not in remote_config:
        raise UserError(_('Unexpected response from Konfoo: %s', response.text))

    if remote_config.get('requires_key') is True and not client_id:
        raise UserError(_('Konfoo Client ID not configured'))

    if not sync_url:
        raise UserError(_('Konfoo Sync URL not configured'))

    if not sync_key:
        raise UserError(_('Konfoo Sync Key not configured'))

    response = requests.get(sync_url, headers={'x-api-key': sync_key})
    if not response:
        raise UserError(_('Could not establish connection to Konfoo Sync: %s', str(response)))

    logger.info('Konfoo connection test OK: %s', profile)
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'message': _('Konfoo connections OK (%s)', profile),
            'type': 'success',
            'sticky': False,
        }
    }


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    konfoo_url = fields.Char(related='company_id.konfoo_url', readonly=False)
    konfoo_url_staging = fields.Char(related='company_id.konfoo_url_staging', readonly=False)
    konfoo_client_id = fields.Char(related='company_id.konfoo_client_id', readonly=False)
    konfoo_client_id_staging = fields.Char(related='company_id.konfoo_client_id_staging', readonly=False)
    konfoo_sync_host = fields.Char(related='company_id.konfoo_sync_host', readonly=False)
    konfoo_sync_host_staging = fields.Char(related='company_id.konfoo_sync_host_staging', readonly=False)
    konfoo_sync_key = fields.Char(related='company_id.konfoo_sync_key', readonly=False)
    konfoo_sync_key_staging = fields.Char(related='company_id.konfoo_sync_key_staging', readonly=False)
    konfoo_product_lookup_field = fields.Char(related='company_id.konfoo_product_lookup_field', readonly=False)
    konfoo_sync_batch_size = fields.Integer(related='company_id.konfoo_sync_batch_size', readonly=False)
    konfoo_default_uom_id = fields.Many2one(related='company_id.konfoo_default_uom_id', readonly=False)

    def action_konfoo_test_connection_staging(self):
        self.ensure_one()
        record = self.with_company(self.company_id)
        return test_konfoo_connection(
            'staging',
            record.konfoo_url_staging,
            record.konfoo_client_id_staging,
            record.konfoo_sync_host_staging,
            record.konfoo_sync_key_staging
        )

    def action_konfoo_test_connection_production(self):
        self.ensure_one()
        record = self.with_company(self.company_id)
        return test_konfoo_connection(
            'live',
            record.konfoo_url,
            record.konfoo_client_id,
            record.konfoo_sync_host,
            record.konfoo_sync_key
        )
