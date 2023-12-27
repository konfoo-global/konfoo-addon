from odoo.tests import TransactionCase, tagged
import json

import logging
logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestKonfooCreateObjects(TransactionCase):

    def test_create_product(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        template_product = self.env['product.product'].create({
            'name': '[MOCK] Product Template',
            'type': 'product',
            'default_code': 'TEMPLATE-ID'
        })

        data = json.loads("""
            {
              "__id__": "mock",
              "model": "product.product",
              "name": "My Product",
              "barcode": "1234567890",
              "template := product.product.default_code": "TEMPLATE-ID"
            }
        """)

        model, create, template_object = konfoo.process_agg_line_struct(data)
        self.assertEqual(model, self.env['product.product'])
        self.assertDictEqual(create, dict(name='My Product', barcode='1234567890'))
        self.assertEqual(template_object, template_product)

        result = konfoo.create_object(model, create, template_object)
        self.assertEqual(result.barcode, '1234567890')
        self.assertEqual(result.name, 'My Product')

    def test_create_bom_component(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        template_main = self.env['product.product'].create({
            'name': '[MOCK] Product Template',
            'type': 'product',
            'default_code': 'KONFOO-TEMPLATE'
        })

        product = self.env['product.product'].create({
            'name': '[MOCK] Mock Product',
            'type': 'product',
            'default_code': 'PROD1234'
        })

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': template_main.product_tmpl_id.id,
        })

        data = json.loads("""
            {
              "__id__": "mock",
              "model": "mrp.bom.line",
              "product_id := product.product.default_code": "PROD1234",
              "product_qty": 1,
              "product_uom_id := uom.uom.name": "Units"
            }
        """)

        model, create, template_object = konfoo.process_agg_line_struct(data, additional_data=dict(bom_id=bom.id))
        self.assertEqual(model, self.env['mrp.bom.line'])
        self.assertEqual(template_object, None)
        self.assertSetEqual(set(create.keys()), {'bom_id', 'product_id', 'product_qty', 'product_uom_id'})
        self.assertEqual(create['product_qty'], 1)

        bom_line = konfoo.create_object(model, create, template_object)
        self.assertTrue(bool(bom_line))
        self.assertEqual(bom_line.product_id, product)
        self.assertEqual(bom_line.product_qty, 1)
        self.assertEqual(bom_line.bom_id, bom)

    def test_create_bom_operation(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        template_main = self.env['product.product'].create({
            'name': '[MOCK] Product Template',
            'type': 'product',
            'default_code': 'KONFOO-TEMPLATE'
        })

        workcenter = self.env['mrp.workcenter'].create({
            'name': '[MOCK] Workcenter',
            'code': 'WC1234',
        })

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': template_main.product_tmpl_id.id,
        })

        data = json.loads("""
            {
              "__id__": "mock",
              "model": "mrp.routing.workcenter",
              "workcenter_id := mrp.workcenter.code": "WC1234",
              "name": "Override",
              "time_cycle_manual": 60
            }
        """)

        model, create, template_object = konfoo.process_agg_line_struct(data, additional_data=dict(bom_id=bom.id))
        self.assertEqual(model, self.env['mrp.routing.workcenter'])
        self.assertIsNone(template_object)
        self.assertSetEqual(set(create.keys()), {'bom_id', 'workcenter_id', 'name', 'time_cycle_manual'})
        self.assertEqual(create['name'], 'Override')
        self.assertEqual(create['time_cycle_manual'], 60)
        self.assertEqual(create['workcenter_id'], workcenter.id)

        bom_op = konfoo.create_object(model, create, template_object)
        self.assertTrue(bool(bom_op))
        self.assertEqual(bom_op.workcenter_id, workcenter)
        self.assertEqual(bom_op.time_cycle_manual, 60)
        self.assertEqual(bom_op.name, "Override")
        self.assertEqual(bom_op.bom_id, bom)

    def test_referenced_purchase_product(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)

        template_main = self.env['product.product'].create({
            'name': '[MOCK] Product Template',
            'type': 'product',
            'default_code': 'PROD1234'
        })

        self.env['product.product'].create({
            'name': '[MOCK] Purchase Product Template',
            'type': 'product',
            'default_code': 'TEMPLATE-ID'
        })

        data = json.loads("""
            [{
              "__id__": "purchase_product",
              "__instance__": "01G1FT8XZKH39NNQ99ZJEKT1W4",
              "model": "product.product",
              "barcode": "1234567890",
              "name": "[MOCK] Purchase Product",
              "template := product.product.default_code": "TEMPLATE-ID"
            },
            {
              "__id__": "bom_line",
              "__instance__": "01G1FT8XZKH39NNQ99ZJEKT1W4",
              "model": "mrp.bom.line",
              "product_id := id": "purchase_product",
              "product_qty": 2,
              "product_uom_id := uom.uom.name": "Units"
            }]
        """)

        bom, created_objects = konfoo.process_aggregated_data(template_main.product_tmpl_id.id, dict(data=data), parent=None)
        self.assertTrue(bool(bom))
        self.assertEqual(len(created_objects), 2)
        self.assertEqual(len(bom.bom_line_ids), 1)

        bom_line = bom.bom_line_ids[0]
        self.assertTrue(bool(bom_line))
        self.assertTrue(bool(bom_line.product_id))
        self.assertEqual(bom_line.product_id.name, "[MOCK] Purchase Product")
        self.assertEqual(bom_line.product_id.barcode, "1234567890")
        self.assertEqual(bom_line.product_qty, 2)
