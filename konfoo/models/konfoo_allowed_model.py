from odoo import models, fields, api
from odoo.release import version_info

import logging
logger = logging.getLogger(__name__)


class KonfooAllowedModel(models.Model):
    _name = 'konfoo.allowed.model'
    _description = 'Konfoo allowed models'
    _rec_name = 'model'

    if version_info[:2] < (19, 0):
        _sql_constraints = [
            ('model_uniq', 'unique(model)', "Model entry already exists"),
        ]
    else:
        _model_uniq = models.Constraint('unique(model)', "Model entry already exists")

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, required=True)
    model = fields.Selection(selection='_list_all_models', string='Model', required=True)

    @api.model
    def _list_all_models(self):
        # TODO: handle translatable model name properly
        self._cr.execute("SELECT model, model FROM ir_model ORDER BY model")
        options = self._cr.fetchall()
        return options
