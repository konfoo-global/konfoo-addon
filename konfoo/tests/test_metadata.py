from odoo.tests import tagged
from odoo.release import version_info
from .konfoo_case import KonfooCase
import json

import logging
logger = logging.getLogger(__name__)

UOM_FIELD = 'product_uom_id' if version_info[:2] <= (19, 0) else 'uom_id'


@tagged('-at_install', 'post_install')
class TestKonfooMetadata(KonfooCase):

    def setUp(self):
        super().setUp()

        self.mock_product = self._create_mock_product({
            'name': '[MOCK] Product',
            'default_code': 'MOCK-PRODUCT'
        })
        self.mock_konfoo_template = self._create_mock_product({
            'name': '[MOCK] Konfoo Template',
            'default_code': 'MOCK-KONFOO-TEMPLATE'
        })

    def test_metadata_1(self):
        konfoo = self.konfoo()

        data = json.loads("""
            {
                "data": [
                    {
                        "__id__": "bom_line",
                        "__instance__": "01YYYYYYYYYYYYYYYYYYYYYYYY",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "MOCK-PRODUCT",
                        "product_qty": 2,
                        "%s := uom.uom.name": "Units"
                    }
                ],
                "meta": {
                    "name": "Mock Configured Product",
                    "description": "<b>Product Description</b>",
                    "template_product": "MOCK-KONFOO-TEMPLATE",
                    "product_name_delimiter": "-",
                    "parent.origin": "Made by Konfoo",
                    "line.name": "SO Line Name"
                },
                "name": "Test Aggregator"
            }
        """ % (UOM_FIELD,))

        mock_partner = self.env['res.partner'].create({
            'name': 'Mock Partner',
            'lang': 'en_US',
        })

        order = self.env['sale.order'].create({
            'partner_id': mock_partner.id,
        })

        self.assertEqual(len(order.order_line), 0)

        ctx = konfoo.configure()
        konfoo.process_konfoo_session(ctx, '01XXXXXXXXXXXXXXXXXXXXXXXX', dict(), data, order, 'sale.order.line')
        self.assertEqual(order.origin, 'Made by Konfoo')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.name, 'SO Line Name')
        self.assertEqual(order.order_line.product_id.description, '<b>Product Description</b>')
        self.assertEqual(order.order_line.product_id.name, f'{order.name}-Mock Configured Product')

        # test updating
        data['meta']['line.name'] = 'Updated Line Name'
        konfoo.process_konfoo_session(ctx, '01XXXXXXXXXXXXXXXXXXXXXXXX', dict(), data, order, 'sale.order.line')

        self.assertEqual(order.origin, 'Made by Konfoo')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.name, 'Updated Line Name')
        self.assertEqual(order.order_line.product_id.description, '<b>Product Description</b>')

    def test_metadata_2(self):
        konfoo = self.konfoo()

        self.env['res.lang']._activate_lang('et_EE')
        self.company.partner_id.write(dict(lang='et_EE'))

        data = json.loads("""
            {
                "data": [],
                "meta": {
                    "name": {
                        "et_EE": "Mock Configured Product EE",
                        "en_US": "Mock Configured Product US"
                    },
                    "description": {
                        "et_EE": "<b>Product Description EE</b>",
                        "en_US": "<b>Product Description US</b>"
                    },
                    "template_product": "MOCK-KONFOO-TEMPLATE",
                    "product_name_delimiter": "-",
                    "parent.origin": "Made by Konfoo"
                },
                "name": "Test Aggregator"
            }
        """)

        mock_partner = self.env['res.partner'].create({
            'name': 'Mock Partner',
            'lang': 'et_EE',
        })

        order = self.env['sale.order'].create({
            'partner_id': mock_partner.id,
        })

        self.assertEqual(len(order.order_line), 0)

        ctx = konfoo.configure()
        konfoo.process_konfoo_session(ctx, '02XXXXXXXXXXXXXXXXXXXXXXXX', dict(), data, order, 'sale.order.line')
        self.assertEqual(order.origin, 'Made by Konfoo')
        self.assertEqual(len(order.order_line), 1)
        self.assertEqual(order.order_line.name, f'{order.name}-Mock Configured Product EE')
        self.assertEqual(order.order_line.product_id.description, '<b>Product Description US</b>')
        self.assertEqual(order.order_line.product_id.name, f'{order.name}-Mock Configured Product US')
