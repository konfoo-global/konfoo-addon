from odoo import models, fields

import logging
logger = logging.getLogger(__name__)


class KonfooDatasetObject(models.Model):
    _name = 'konfoo.dataset_object'
    _description = 'Dataset Object'
    _sql_constraints = [
        ('cache_index', 'unique(dataset_id, res_id)', "Cache entry must have unique references"),
    ]

    dataset_id = fields.Many2one('konfoo.dataset', 'Dataset', required=True)
    res_id = fields.Integer('Resource ID', required=True)
    sync_date = fields.Datetime('Synced on', index=True, readonly=True, required=True)
