from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

import logging
logger = logging.getLogger(__name__)

CSV_COLUMN_NAME_VALIDATOR = re.compile(r'[^\w\d\-_\. ]') # noqa


# noinspection PyAbstractClass
class ModelFieldSelection(fields.Selection):
    def convert_to_cache(self, value, record, validate=True):
        if not validate:
            return value or None
        if value and self.column_type[0] == 'int4':
            value = int(value)
        if not value:
            return None
        return value


class KonfooDatasetField(models.Model):
    _name = 'konfoo.dataset_field'
    _description = 'Dataset Field'
    _sql_constraints = [
        ('uniq', 'unique(dataset_id, name)', "Dataset fields must be unique"),
    ]

    dataset_id = fields.Many2one('konfoo.dataset', 'Dataset', required=True)
    name = ModelFieldSelection(selection='_list_model_fields', string='Name', required=True)
    csv_name = fields.Char('CSV Column', required=True)
    is_unique = fields.Boolean('Unique Index', required=True)
    is_group = fields.Boolean('Group Index', required=True)

    def _list_model_fields(self):
        dataset_id = self.env.context.get('default_dataset_id')
        if not dataset_id:
            return []
        self._cr.execute(
            """
            select name, name
            from ir_model_fields
            where model = (select model_id from konfoo_dataset where id = %s) and name != 'id'
            order by name asc
            """,
            (dataset_id,))
        options = self._cr.fetchall()
        return options

    @api.constrains('csv_name')
    def _check_name(self):
        for record in self:
            if not record.csv_name or len(record.csv_name) == 0:
                raise ValidationError(_('CSV column name cannot be empty'))
            if bool(CSV_COLUMN_NAME_VALIDATOR.search(record.csv_name)):
                raise ValidationError(_('CSV column name %s contains forbidden characters', record.csv_name))

    @api.onchange('name')
    def _onchange_name(self):
        for record in self:
            if not record.name:
                continue
            record.csv_name = record.name
