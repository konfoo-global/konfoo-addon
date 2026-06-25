from odoo.tests import tagged
from odoo.release import version_info
from .konfoo_case import KonfooCase
import json

import logging
logger = logging.getLogger(__name__)

UOM_FIELD = 'product_uom_id' if version_info[:2] <= (19, 0) else 'uom_id'

@tagged('-at_install', 'post_install')
class TestKonfooUpdateObjects(KonfooCase):

    def test_update_created_object(self):
        konfoo = self.konfoo()

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
                    "%s := uom.uom.name": "Units",
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
                    "method": "action_archive",
                    "model": "product.product",
                    "records": "(search) [('default_code', '=', 'BOM-PRODUCT-COPY'), ('id', '=', product_copy)] {'limit': 1}"
                }
            ]
        """ % (UOM_FIELD,))

        bom, processed_objects = konfoo.process_aggregated_data(self.template_product.product_tmpl_id, dict(data=data), parent=None)
        self.assertEqual(len(processed_objects), 4)

        created_product = processed_objects[0]
        self.assertEqual(created_product.name, "[MOCK] BoM Product Copy")
        self.assertEqual(created_product.active, False)

        created_bom_line = processed_objects[1]
        self.assertEqual(created_bom_line.product_id.id, created_product.id)
        self.assertEqual(created_bom_line.product_qty, 2)

    def test_read_object(self):
        konfoo = self.konfoo()

        product = self._create_mock_product({
            'name': '[MOCK] Read Product',
            'default_code': 'READ-PRODUCT'
        })

        agg_line = json.loads("""
            {
                "__id__": "product_read",
                "__instance__": "01J7ZJX51S506Y8P514P1Y2CNJ",
                "command": "read",
                "model": "product.product",
                "records": "(search) [('default_code', '=', 'READ-PRODUCT')]"
            }
        """)

        processed_object = konfoo.process_aggregated_data_line(agg_line, None, map_cache_objects=dict())
        self.assertEqual(processed_object.default_code, product.default_code)
        self.assertEqual(processed_object.name, product.name)
        self.assertEqual(processed_object.type, product.type)

    def test_parse_records_lookup(self):
        konfoo = self.konfoo()

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
