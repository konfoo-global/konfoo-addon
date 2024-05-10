import urllib3.exceptions

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from urllib.parse import urljoin
import requests
import json
import gzip
import base64

import logging
logger = logging.getLogger(__name__)


def unwrap_requests_exception(err):
    if isinstance(err, requests.exceptions.ConnectionError) and err.args:
        err = err.args[0]

    if isinstance(err, urllib3.exceptions.MaxRetryError) and err.reason:
        err = err.reason

    if isinstance(err, urllib3.exceptions.NewConnectionError) and err.conn:  # noqa
        return err

    return err


def test_konfoo_connection(profile, konfoo_url, client_id, sync_url, sync_key):
    if not konfoo_url:
        raise ValidationError(_('Konfoo URL not configured'))

    try:
        response = requests.get(urljoin(konfoo_url, '/api/v1/state'))
    except Exception as err:
        err = unwrap_requests_exception(err)  # noqa
        msg = str(err)
        raise ValidationError(_('Failed to establish connection to Konfoo: %s', msg))

    if not response:
        raise ValidationError(_('Could not establish connection to Konfoo: %s', str(response)))
    try:
        remote_config = response.json()
    except json.JSONDecodeError:
        raise ValidationError(_('Unexpected response from Konfoo: %s', response.text))

    if 'requires_key' not in remote_config:
        raise ValidationError(_('Unexpected response from Konfoo: %s', response.text))

    if remote_config.get('requires_key') is True and not client_id:
        raise ValidationError(_('Konfoo Client ID not configured'))

    if not sync_url:
        raise ValidationError(_('Konfoo Sync URL not configured'))

    if not sync_key:
        raise ValidationError(_('Konfoo Sync Key not configured'))

    try:
        response = requests.get(sync_url, headers={'x-api-key': sync_key})
    except Exception as err:
        err = unwrap_requests_exception(err)  # noqa
        msg = str(err)
        raise ValidationError(_('Failed to establish connection to Konfoo Sync: %s', msg))
    if not response:
        raise ValidationError(_('Could not establish connection to Konfoo Sync: %s', str(response)))

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

    konfoo_config_blob = fields.Text(
        'Auto Configuration', compute='konfoo_compute_config_blob', inverse='konfoo_parse_config_blob')

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

    @api.depends(
        'konfoo_url',
        'konfoo_url_staging',
        'konfoo_client_id',
        'konfoo_client_id_staging',
        'konfoo_sync_host',
        'konfoo_sync_host_staging',
        'konfoo_sync_key',
        'konfoo_sync_key_staging',
        'konfoo_product_lookup_field',
        'konfoo_sync_batch_size',
        'konfoo_default_uom_id',
    )
    def konfoo_compute_config_blob(self):
        for record in self:
            config = dict(
                stg=dict(
                    url=record.konfoo_url_staging,
                    cid=record.konfoo_client_id_staging,
                    syn=record.konfoo_sync_host_staging,
                    sid=record.konfoo_sync_key_staging,
                ),
                prd=dict(
                    url=record.konfoo_url,
                    cid=record.konfoo_client_id,
                    syn=record.konfoo_sync_host,
                    sid=record.konfoo_sync_key,
                ),
                plf=record.konfoo_product_lookup_field,
                bsz=record.konfoo_sync_batch_size,
                uom=record.konfoo_default_uom_id.id,
            )
            compressed = gzip.compress(json.dumps(config).encode())
            record.konfoo_config_blob = base64.b64encode(compressed)

    def konfoo_parse_config_blob(self):
        for record in self:
            if not record.konfoo_config_blob:
                continue
            try:
                decoded = base64.b64decode(record.konfoo_config_blob)
                uncompressed = gzip.decompress(decoded)
                config = json.loads(uncompressed)

                # TODO: proper schema for marshaling data
                if config.get('stg'):
                    record.konfoo_url_staging = config.get('stg').get('url')
                    record.konfoo_client_id_staging = config.get('stg').get('cid')
                    record.konfoo_sync_host_staging = config.get('stg').get('syn')
                    record.konfoo_sync_key_staging = config.get('stg').get('sid')

                if config.get('prd'):
                    record.konfoo_url = config.get('prd').get('url')
                    record.konfoo_client_id = config.get('prd').get('cid')
                    record.konfoo_sync_host = config.get('prd').get('syn')
                    record.konfoo_sync_key = config.get('prd').get('sid')

                record.konfoo_product_lookup_field = config.get('plf', 'default_code')
                record.konfoo_sync_batch_size = config.get('bsz', 100)
                record.konfoo_default_uom_id = config.get('uom', False)
            except Exception as err:
                logger.error(err)
