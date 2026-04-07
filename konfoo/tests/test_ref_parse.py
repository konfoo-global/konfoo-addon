from odoo.tests import tagged
from .konfoo_case import KonfooCase

import logging
logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestKonfooRefParse(KonfooCase):

    def test_parse_odoo_ref(self):
        konfoo = self.konfoo()

        model, field = konfoo.parse_odoo_ref('product.product.default_code')
        self.assertEqual(model, 'product.product')
        self.assertEqual(field, 'default_code')

        model, field = konfoo.parse_odoo_ref('product.product . default_code')
        self.assertEqual(model, 'product.product')
        self.assertEqual(field, 'default_code')

        model, field = konfoo.parse_odoo_ref('definitely.does.not.exist')
        self.assertEqual(model, None)
        self.assertEqual(field, None)

    def test_parse_konfoo_lookup(self):
        konfoo = self.konfoo()

        lookup = konfoo.parse_assignment('product_id := product.product.default_code')
        self.assertIsNotNone(lookup)
        self.assertEqual(lookup.target_field, 'product_id')
        self.assertEqual(lookup.lookup_model, self.env['product.product'])
        self.assertEqual(lookup.lookup_field, 'default_code')

        lookup = konfoo.parse_assignment('product_id:=product.product.default_code')
        self.assertIsNotNone(lookup)
        self.assertEqual(lookup.target_field, 'product_id')
        self.assertEqual(lookup.lookup_model, self.env['product.product'])
        self.assertEqual(lookup.lookup_field, 'default_code')

        lookup = konfoo.parse_assignment('product_id:=definitely.does.not.exist')
        self.assertIsNone(lookup)

    def test_parse_ref_lookup(self):
        konfoo = self.konfoo()

        product = self._create_mock_product({
            'name': '[MOCK] Mock Product',
            'default_code': 'PROD1234'
        })

        lookup = konfoo.parse_ref_assignment('product_id := id', 'mock_rule_id', 'MOCKINSTANCEID', dict())
        self.assertIsNone(lookup)

        lookup = konfoo.parse_ref_assignment('product_id := id', 'mock_rule_id', 'MOCKINSTANCEID', {
            'mock_rule_id-MOCKINSTANCEID': product
        })
        self.assertEqual(lookup.lookup_field, 'id')
        self.assertEqual(lookup.get(), product)
        self.assertEqual(lookup.value(), product.id)
