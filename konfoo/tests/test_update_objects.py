from odoo.tests import TransactionCase, tagged
from odoo.release import version_info
import json

import logging
logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestKonfooUpdateObjects(TransactionCase):

    def _create_mock_product(self, values):
        if version_info[:2] < (18, 0):
            values['type'] = 'product'
        else:
            values['is_storable'] = True
        return self.env['product.product'].create(values)

    def test_update_created_object(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        template_main = self._create_mock_product({
            'name': '[MOCK] Konfoo Template',
            'default_code': 'KONFOO-TEMPLATE'
        })

        self._create_mock_product({
            'name': '[MOCK] BoM Product',
            'default_code': 'BOM-PRODUCT'
        })

        data = json.loads("""
            [
                {
                    "__id__": "product_copy",
                    "__instance__": "01J7ZJX51S506Y8P514P1Y2CNJ",
                    "model": "product.product",
                    "name": "[MOCK] BoM Product Copy",
                    "default_code": "BOM-PRODUCT-COPY",
                    "template := product.product.default_code": "BOM-PRODUCT"
                },
                {
                    "__id__": "bom_line_create",
                    "__instance__": "01J7ZJX51S506Y8P514P1Y2CNJ",
                    "model": "mrp.bom.line",
                    "product_id := product.product.default_code": "BOM-PRODUCT-COPY",
                    "product_uom_id := uom.uom.name": "Units",
                    "product_qty": 1
                },
                {
                    "__id__": "bom_line_update",
                    "__instance__": "01J7ZJX51S506Y8P514P1Y2CNJ",
                    "command": "write",
                    "model": "mrp.bom.line",
                    "records": "(search) [('id', '=', bom_line_create)]",
                    "product_qty": 2
                },
                {
                    "__id__": "product_archive",
                    "__instance__": "01J7ZJX51S506Y8P514P1Y2CNJ",
                    "command": "rpc",
                    "method": "toggle_active",
                    "model": "product.product",
                    "records": "(search) [('default_code', '=', 'BOM-PRODUCT-COPY'), ('id', '=', product_copy)] {'limit': 1}"
                }
            ]
        """)

        bom, processed_objects = konfoo.process_aggregated_data(template_main.product_tmpl_id.id, dict(data=data), parent=None)
        self.assertEqual(len(processed_objects), 2)

        created_product = processed_objects[0]
        self.assertEqual(created_product.name, "[MOCK] BoM Product Copy")
        self.assertEqual(created_product.active, False)

        created_bom_line = processed_objects[1]
        self.assertEqual(created_bom_line.product_id.id, created_product.id)
        self.assertEqual(created_bom_line.product_qty, 2)

    def test_parse_records_lookup(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        product = self._create_mock_product({
            'name': '[MOCK] Product Copy',
            'default_code': 'PRODUCT-COPY'
        })

        lookup = konfoo.parse_records_search('product.product', 123.4, 'MOCKINSTANCEID', dict())
        self.assertIsNone(lookup)

        lookup = konfoo.parse_records_search('product.product', 12345, 'MOCKINSTANCEID', dict())
        self.assertEqual(lookup.lookup_domain, [('id', '=', 12345)])
        self.assertEqual(lookup.lookup_kwargs, dict())

        input_value = "(search) [('default_code', '=', 'PRODUCT-COPY')]"
        lookup = konfoo.parse_records_search('product.product', input_value, 'MOCKINSTANCEID', dict())
        self.assertEqual(lookup.lookup_domain, [('default_code', '=', 'PRODUCT-COPY')])
        self.assertEqual(lookup.lookup_kwargs, dict())

        input_value = "(search) [('id', '=', product_copy)] {'limit': 1}"
        objects_map = {'product_copy-MOCKINSTANCEID': product}
        lookup = konfoo.parse_records_search('product.product', input_value, 'MOCKINSTANCEID', objects_map)
        self.assertEqual(lookup.lookup_domain, [('id', '=', product.id)])
        self.assertEqual(lookup.lookup_kwargs, dict(limit=1))
