from odoo.tests import tagged
from odoo.addons.konfoo.models.konfoo_api import make_cache_key # noqa
from .konfoo_case import KonfooCase
import json

import logging
_logger = logging.getLogger(__name__)

TEST_BOM_DATA = json.loads("""
{
  "data": [
    {
      "__id__": "create_product_from_template",
      "__instance__": "01GHE6VEQ18EYG74HJAPB1J45W",
      "model": "product.product",
      "template := product.product.default_code": "PRODUCT-TEMPLATE",
      "name": "{{parent.name}}: some additional info",
      "default_code": "{{parent.name}}-P1234"
    }
  ],
  "meta": {
    "name": "SO-PRODUCT-NAME",
    "template_product": "KONFOO-TEMPLATE",
    "enable_interpolation": true
  },
  "name": "Bill of materials"
}
""")


@tagged('-at_install', 'post_install')
class TestInterpolation(KonfooCase):

    def test_reference_parent(self):
        konfoo = self.konfoo()

        self._create_mock_product({
            'name': 'Template Product',
            'default_code': 'PRODUCT-TEMPLATE'
        })

        ctx = konfoo.configure()
        konfoo.process_konfoo_session(ctx, '01XXXXXXXXXXXXXXXXXXXXXXXX', dict(), TEST_BOM_DATA, self.sale_order, 'sale.order.line')

        created_product = self.env['product.product'].search([('default_code', '=', f'{self.sale_order.name}-P1234')])
        self.assertTrue(created_product)
        self.assertEqual(created_product.name, f'{self.sale_order.name}: some additional info')
