from odoo import fields
from odoo.fields import Default

import logging
logger = logging.getLogger(__name__)


class DynamicSelection(fields.Selection):
    def __init__(self, selection_dynamic=Default, string=Default, **kwargs):
        super(DynamicSelection, self).__init__(
            selection=[('selection_dynamic', selection_dynamic)],
            selection_dynamic=selection_dynamic,
            string=string,
            **kwargs)
        self.selection_dynamic = selection_dynamic

    def convert_to_cache(self, value, record, validate=True):
        if not validate:
            return value or None
        if value and self.column_type[0] == 'int4':
            value = int(value)
        if not value:
            return None
        return value
