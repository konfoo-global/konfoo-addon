from odoo.tests import TransactionCase, tagged
from odoo.release import version_info
import json

import logging
logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestKonfooMetadata(TransactionCase):

    def setUp(self):
        super().setUp()

        company = self.env.user.company_id

        # NOTE: the values do not matter 'cause we avoid doing any requests
        company.konfoo_url = company.konfoo_url_staging = 'http://localhost:8000'
        company.konfoo_client_id_staging = company.konfoo_client_id = 'test'
        company.konfoo_default_uom_id = self.env.ref('uom.product_uom_unit').id

        if version_info[:2] < (18, 0):
            self.env['product.product'].create({
                'name': '[MOCK] Product',
                'type': 'product',
                'default_code': 'MOCK-PRODUCT'
            })
            self.env['product.product'].create({
                'name': '[MOCK] Konfoo Template',
                'type': 'product',
                'default_code': 'MOCK-KONFOO-TEMPLATE'
            })
        else:
            self.env['product.product'].create({
                'name': '[MOCK] Product',
                'is_storable': True,
                'default_code': 'MOCK-PRODUCT'
            })
            self.env['product.product'].create({
                'name': '[MOCK] Konfoo Template',
                'is_storable': True,
                'default_code': 'MOCK-KONFOO-TEMPLATE'
            })

    def test_metadata_1(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        data = json.loads("""
            {
                "data": [
                    {
                        "__id__": "bom_line",
                        "__instance__": "01YYYYYYYYYYYYYYYYYYYYYYYY",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "MOCK-PRODUCT",
                        "product_qty": 2,
                        "product_uom_id := uom.uom.name": "Units"
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
        """)

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
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        self.env['res.lang']._activate_lang("et_EE")

        data = json.loads("""
            {
                "data": [
                    {
                        "__id__": "bom_line",
                        "__instance__": "02YYYYYYYYYYYYYYYYYYYYYYYY",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "MOCK-PRODUCT",
                        "product_qty": 2,
                        "product_uom_id := uom.uom.name": "Units"
                    }
                ],
                "meta": {
                    "name": {
                        "et_EE": "Test Konfigureeritud Toode",
                        "en_US": "Mock Configured Product",
                        "et_US": "Invalid LANG Option"
                    },
                    "description": {
                        "et_EE": "<b>Toote Kirjeldus</b>",
                        "en_US": "<b>Product Description</b>",
                        "et_US": "<b>Invalid LANG Option</b>"
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
        if version_info[:2] < (16, 0):
            self.assertEqual(order.order_line.name, f'{order.name}-Mock Configured Product')
        else:
            self.assertEqual(order.order_line.name, f'{order.name}-Test Konfigureeritud Toode')
        self.assertEqual(order.order_line.product_id.description, '<b>Product Description</b>')
        self.assertEqual(order.order_line.product_id.name, f'{order.name}-Mock Configured Product')
