from odoo.tests import TransactionCase, tagged, Form
from odoo import fields, release
from odoo.addons.konfoo.models.konfoo_api import make_cache_key # noqa
import json

import logging
logger = logging.getLogger(__name__)

TEST_BOM_DATA = json.loads("""
{
  "data": [
    {
      "__id__": "create_so_line",
      "__instance__": "01GHE6VEQ18EYG74HJAPB1J45W",
      "model": "sale.order.line",
      "name": "Additional SO Line",
      "order_id := parent": "id",
      "product_uom_qty": 2,
      "product_id := product.product.default_code": "TEST"
    }
  ],
  "meta": {
    "name": "SO-PRODUCT-NAME",
    "parent.commitment_date": "2022-11-11",
    "template_product": "KONFOO-TEMPLATE"
  },
  "name": "Bill of materials"
}
""")


@tagged('-at_install', 'post_install')
class TestKonfooSetParentProps(TransactionCase):

    def setUp(self):
        super().setUp()

        self.template_product = self.env['product.product'].create({
            'name': '[MOCK] Product Template',
            'type': 'product',
            'default_code': 'KONFOO-TEMPLATE'
        })

        self.product = self.env['product.product'].create({
            'name': '[MOCK] Mock Product',
            'type': 'product',
            'default_code': 'TEST'
        })

        customer = Form(self.env['res.partner'])
        customer.name = '[MOCK] Customer'

        (MAJOR, _, _, _, _, _THIS_NOT_IN_THE_FORMAT_SPEC) = release.version_info
        if MAJOR <= 14:
            property_account_payable_id = {
                'name': 'Test Account Payable',
                'code': 'TestAccountPayable',
                'reconcile': True,
                'user_type_id': self.env.ref('account.data_account_type_payable').id,
            }
            property_account_receivable_id = {
                'name': 'Test Account Receivable',
                'code': 'TestAccountReceivable',
                'reconcile': True,
                'user_type_id': self.env.ref('account.data_account_type_receivable').id,
            }

            if hasattr(self.env['res.partner'], 'property_account_payable_id'):
                customer.property_account_payable_id = self.env['account.account'].create(property_account_payable_id)
            if hasattr(self.env['res.partner'], 'property_account_receivable_id'):
                customer.property_account_receivable_id = self.env['account.account'].create(property_account_receivable_id)

        self.customer = customer.save()
        self.sale_order = self.env['sale.order'].create({
            'name': 'S00001',
            'partner_id': self.customer.id,
        })

    def test_set_parent_property(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)
        self.assertEqual(self.sale_order.commitment_date, False)

        template_product, product_name, additional_data = konfoo.process_bom_metadata(TEST_BOM_DATA, self.sale_order)
        self.assertEqual(template_product, 'KONFOO-TEMPLATE')
        self.assertEqual(product_name, f'{self.sale_order.name} SO-PRODUCT-NAME')
        self.assertEqual(len(additional_data.keys()), 0)
        self.assertEqual(self.sale_order.commitment_date, fields.Datetime.from_string('2022-11-11'))

    def test_reference_parent(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        line = TEST_BOM_DATA.get('data')[0]
        map_created_objects = dict()
        map_created_objects[make_cache_key('parent', line.get('__instance__', 'anon'))] = self.sale_order

        created_obj = konfoo.process_aggregated_data_line(line, None, map_created_objects=map_created_objects)
        self.assertTrue(bool(created_obj))
        so_line_cache_key = make_cache_key('create_so_line', line.get('__instance__', 'anon'))
        self.assertTrue(so_line_cache_key in map_created_objects)
        self.assertEqual(map_created_objects.get(so_line_cache_key), created_obj)
        self.assertEqual(created_obj.product_uom_qty, 2)
        self.assertEqual(created_obj.product_id.id, self.product.id)
