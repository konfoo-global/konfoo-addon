from odoo import models, fields
from odoo.release import version_info

import logging
logger = logging.getLogger(__name__)


class KonfooDatasetObject(models.Model):
    _name = 'konfoo.dataset_object'
    _description = 'Dataset Object'

    if version_info[:2] < (19, 0):
        _sql_constraints = [
            ('cache_index', 'unique(dataset_id, res_id)', "Cache entry must have unique references"),
        ]
    else:
        _cache_index = models.Constraint('unique(dataset_id, res_id)', "Cache entry must have unique references")

    dataset_id = fields.Many2one('konfoo.dataset', 'Dataset', required=True)
    res_id = fields.Integer('Resource ID', required=True)
    sync_date = fields.Datetime('Synced on', index=True, readonly=True, required=True)
