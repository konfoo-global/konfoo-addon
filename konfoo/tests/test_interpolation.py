from odoo.tests import tagged
from odoo import fields
from odoo.addons.konfoo.models.konfoo_api import make_cache_key # noqa
from .konfoo_case import KonfooCase
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
class TestInterpolation(KonfooCase):

    def test_set_parent_property(self):
        konfoo = self.konfoo()
        pass
        # self.assertEqual(self.sale_order.commitment_date, False)
        #
        # template_product, product_name, additional_data, translated_data, options = konfoo.process_bom_metadata(TEST_BOM_DATA, self.sale_order)
        # self.assertEqual(template_product, 'KONFOO-TEMPLATE')
        # self.assertEqual(product_name, f'{self.sale_order.name} SO-PRODUCT-NAME')
        # self.assertEqual(len(additional_data.keys()), 0)
        # self.assertEqual(len(translated_data.keys()), 1)
        # self.assertEqual(self.sale_order.commitment_date, fields.Datetime.from_string('2022-11-11'))

    # def test_reference_parent(self):
    #     konfoo = self.konfoo()
    #
    #     line = TEST_BOM_DATA.get('data')[0]
    #     map_cache_objects = dict()
    #     map_cache_objects[make_cache_key('parent', line.get('__instance__', 'anon'))] = self.sale_order
    #
    #     created_obj = konfoo.process_aggregated_data_line(line, None, map_cache_objects=map_cache_objects)
    #     self.assertTrue(bool(created_obj))
    #     so_line_cache_key = make_cache_key('create_so_line', line.get('__instance__', 'anon'))
    #     self.assertTrue(so_line_cache_key in map_cache_objects)
    #     self.assertEqual(map_cache_objects.get(so_line_cache_key), created_obj)
    #     self.assertEqual(created_obj.product_uom_qty, 2)
    #     self.assertEqual(created_obj.product_id.id, self.product.id)
