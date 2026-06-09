from odoo.tests import tagged, Form
from odoo.release import version_info
from .konfoo_case import KonfooCase
import json

import logging
logger = logging.getLogger(__name__)

UOM_FIELD = 'product_uom_id' if version_info[:2] <= (19, 0) else 'uom_id'


@tagged('-at_install', 'post_install')
class TestKonfooCreateObjects(KonfooCase):

    def test_create_product(self):
        konfoo = self.konfoo()

        template_product = self._create_mock_product({
            'name': '[MOCK] Product Template',
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

        model, create, template_object, method = konfoo.process_agg_line_struct(data)
        self.assertEqual(model, self.env['product.product'])
        self.assertDictEqual(create, dict(name='My Product', barcode='1234567890'))
        self.assertEqual(template_object, template_product)

        result = konfoo.create_object(model, create, template_object)
        self.assertEqual(result.barcode, '1234567890')
        self.assertEqual(result.name, 'My Product')

    def test_create_bom_component(self):
        konfoo = self.konfoo()

        product = self._create_mock_product({
            'name': '[MOCK] Mock Product',
            'default_code': 'PROD1234'
        })

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.template_product.product_tmpl_id.id,
        })

        data = json.loads("""
            {
              "__id__": "mock",
              "model": "mrp.bom.line",
              "product_id := product.product.default_code": "PROD1234",
              "product_qty": 1,
              "%s := uom.uom.name": "Units"
            }
        """ % (UOM_FIELD,))

        model, create, template_object, method = konfoo.process_agg_line_struct(data, additional_data=dict(bom_id=bom.id))
        self.assertEqual(model, self.env['mrp.bom.line'])
        self.assertEqual(template_object, None)
        self.assertSetEqual(set(create.keys()), {'bom_id', 'product_id', 'product_qty', UOM_FIELD})
        self.assertEqual(create['product_qty'], 1)

        bom_line = konfoo.create_object(model, create, template_object)
        self.assertTrue(bool(bom_line))
        self.assertEqual(bom_line.product_id, product)
        self.assertEqual(bom_line.product_qty, 1)
        self.assertEqual(bom_line.bom_id, bom)

    def test_create_bom_operation(self):
        konfoo = self.konfoo()

        workcenter = self.env['mrp.workcenter'].create({
            'name': '[MOCK] Workcenter',
            'code': 'WC1234',
        })

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.template_product.product_tmpl_id.id,
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

        model, create, template_object, method = konfoo.process_agg_line_struct(data, additional_data=dict(bom_id=bom.id))
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
        konfoo = self.konfoo()

        template_main = self._create_mock_product({
            'name': '[MOCK] Product Template',
            'default_code': 'PROD1234'
        })

        self._create_mock_product({
            'name': '[MOCK] Purchase Product Template',
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
              "%s := uom.uom.name": "Units"
            }]
        """ % (UOM_FIELD,))

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

    def test_yielding_identical_object(self):
        konfoo = self.konfoo()

        company = self.env.user.company_id

        # NOTE: the values do not matter 'cause we avoid doing any requests
        company.konfoo_url = company.konfoo_url_staging = 'http://localhost:8000'
        company.konfoo_client_id_staging = company.konfoo_client_id = 'test'
        company.konfoo_default_uom_id = self.env.ref('uom.product_uom_unit').id
        ctx = konfoo.configure()

        self._create_mock_product({
            'name': '[MOCK] Product Template',
            'default_code': 'KONFOO-TEMPLATE-vqctTr00'
        })

        self._create_mock_product({
            'name': '[MOCK] Component 1',
            'default_code': 'COMPONENT-1'
        })

        partner_form = Form(self.env['res.partner'])
        partner_form.name = 'Test Partner'
        partner = partner_form.save()

        sale_order_form = Form(self.env['sale.order'])
        sale_order_form.partner_id = partner
        sale_order = sale_order_form.save()

        data = json.loads("""
            {
                "meta": {
                    "default_code": "ACIED",
                    "line.price_unit": 123.0,
                    "name": "Initial Name",
                    "template_product": "KONFOO-TEMPLATE-vqctTr00",
                    "use_parent_name_prefix": false,
                    "update_if_exists": "default_code"
                },
                "name": "Bill of materials",
                "data": [
                    {
                        "__id__": "component_1",
                        "__instance__": "01AAAAAAAAAAAAAAAAAAAAAAAA",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "COMPONENT-1",
                        "product_qty": 1,
                        "%s := uom.uom.name": "Units"
                    }
                ]
            }
        """ % (UOM_FIELD,))

        konfoo.process_konfoo_session(ctx, '01SSSSSSSSSSSSSSSSSSSSSSS0', dict(), data, sale_order, 'sale.order.line')

        self.assertEqual(len(sale_order.order_line), 1)

        order_line_0 = sale_order.order_line[0]
        self.assertAlmostEqual(order_line_0.price_unit, 123.0)
        self.assertEqual(order_line_0.product_id.name, 'Initial Name')

        boms_0 = self.env['mrp.bom'].search([('product_tmpl_id', '=', order_line_0.product_id.product_tmpl_id.id)])
        bom_line_ids_0 = boms_0.bom_line_ids.ids
        session_0 = self.env['konfoo.session'].search([('konfoo_session_id', '=', '01SSSSSSSSSSSSSSSSSSSSSSS0')])
        self.assertEqual(len(session_0), 1)
        self.assertEqual(session_0.konfoo_session_id, '01SSSSSSSSSSSSSSSSSSSSSSS0')
        self.assertEqual(order_line_0.product_id.konfoo_session_id.id, session_0.id)
        self.assertEqual(len(boms_0.bom_line_ids), 1)

        data['meta']['name'] = 'Updated Name'
        konfoo.process_konfoo_session(ctx, '01SSSSSSSSSSSSSSSSSSSSSSS1', dict(), data, sale_order, 'sale.order.line')

        self.assertEqual(len(sale_order.order_line), 2)
        self.assertEqual(sale_order.order_line[0].id, order_line_0.id)

        order_line_1 = sale_order.order_line[1]
        self.assertAlmostEqual(order_line_1.price_unit, 123.0)
        self.assertEqual(order_line_1.product_id.name, 'Updated Name')
        self.assertEqual(order_line_0.product_id.name, 'Updated Name')
        self.assertEqual(order_line_0.product_id.id, order_line_1.product_id.id)

        boms_1 = self.env['mrp.bom'].search([('product_tmpl_id', '=', order_line_1.product_id.product_tmpl_id.id)])
        bom_line_ids_1 = boms_1.bom_line_ids.ids
        self.assertEqual(boms_0.ids, boms_1.ids)
        self.assertEqual(len(boms_1.bom_line_ids), 1)
        self.assertNotEqual(bom_line_ids_0, bom_line_ids_1)  # should be fresh lines in the bom

        session_1 = self.env['konfoo.session'].search([('konfoo_session_id', '=', '01SSSSSSSSSSSSSSSSSSSSSSS1')])
        self.assertEqual(len(session_1), 1)
        self.assertEqual(session_1.konfoo_session_id, '01SSSSSSSSSSSSSSSSSSSSSSS1')
        self.assertEqual(order_line_1.product_id.konfoo_session_id.id, session_1.id)
        self.assertEqual(order_line_0.product_id.konfoo_session_id.id, session_1.id)

    def test_seller_ids_copied_for_main_product(self):
        konfoo = self.konfoo()

        company = self.env.user.company_id

        # NOTE: the values do not matter 'cause we avoid doing any requests
        company.konfoo_url = company.konfoo_url_staging = 'http://localhost:8000'
        company.konfoo_client_id_staging = company.konfoo_client_id = 'test'
        company.konfoo_default_uom_id = self.env.ref('uom.product_uom_unit').id
        ctx = konfoo.configure()

        template_product = self._create_mock_product({
            'name': '[MOCK] Product Template',
            'default_code': 'KONFOO-TEMPLATE-sellers-rN8wq1'
        })

        self._create_mock_product({
            'name': '[MOCK] Component 1',
            'default_code': 'COMPONENT-sellers-rN8wq1'
        })

        supplier_form = Form(self.env['res.partner'])
        supplier_form.name = '[MOCK] Supplier'
        supplier = supplier_form.save()

        self.env['product.supplierinfo'].create({
            'product_tmpl_id': template_product.product_tmpl_id.id,
            'partner_id': supplier.id,
            'price': 42.0,
        })

        partner_form = Form(self.env['res.partner'])
        partner_form.name = 'Test Partner'
        partner = partner_form.save()

        sale_order_form = Form(self.env['sale.order'])
        sale_order_form.partner_id = partner
        sale_order = sale_order_form.save()

        data = json.loads("""
            {
                "meta": {
                    "name": "Product With Sellers",
                    "template_product": "KONFOO-TEMPLATE-sellers-rN8wq1"
                },
                "name": "Bill of materials",
                "data": [
                    {
                        "__id__": "component_1",
                        "__instance__": "01SELLERAAAAAAAAAAAAAAAAAA",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "COMPONENT-sellers-rN8wq1",
                        "product_qty": 1,
                        "%s := uom.uom.name": "Units"
                    }
                ]
            }
        """ % (UOM_FIELD,))

        konfoo.process_konfoo_session(ctx, '01SELLERSSSSSSSSSSSSSSSSS0', dict(), data, sale_order, 'sale.order.line')

        self.assertEqual(len(sale_order.order_line), 1)

        created_product = sale_order.order_line[0].product_id
        self.assertEqual(len(created_product.product_tmpl_id.seller_ids), 1)
        self.assertEqual(created_product.product_tmpl_id.seller_ids[0].partner_id, supplier)
        self.assertAlmostEqual(created_product.product_tmpl_id.seller_ids[0].price, 42.0)

    def test_use_existing_if_exists(self):
        konfoo = self.konfoo()

        company = self.env.user.company_id

        # NOTE: the values do not matter 'cause we avoid doing any requests
        company.konfoo_url = company.konfoo_url_staging = 'http://localhost:8000'
        company.konfoo_client_id_staging = company.konfoo_client_id = 'test'
        company.konfoo_default_uom_id = self.env.ref('uom.product_uom_unit').id
        ctx = konfoo.configure()

        self._create_mock_product({
            'name': '[MOCK] Product Template',
            'default_code': 'KONFOO-TEMPLATE-w3kvp6tp'
        })

        self._create_mock_product({
            'name': '[MOCK] Component 1',
            'default_code': 'COMPONENT-1'
        })

        partner_form = Form(self.env['res.partner'])
        partner_form.name = 'Test Partner'
        partner = partner_form.save()

        sale_order_form = Form(self.env['sale.order'])
        sale_order_form.partner_id = partner
        sale_order = sale_order_form.save()

        data = json.loads("""
            {
                "meta": {
                    "default_code": "ACIED",
                    "line.price_unit": 123.0,
                    "name": "Initial Name",
                    "template_product": "KONFOO-TEMPLATE-w3kvp6tp",
                    "use_parent_name_prefix": false,
                    "use_if_exists": "default_code"
                },
                "name": "Bill of materials",
                "data": [
                    {
                        "__id__": "component_1",
                        "__instance__": "01AAAAAAAAAAAAAAAAAAAAAAAA",
                        "model": "mrp.bom.line",
                        "product_id := product.product.default_code": "COMPONENT-1",
                        "product_qty": 1,
                        "%s := uom.uom.name": "Units"
                    }
                ]
            }
        """ % (UOM_FIELD,))

        konfoo.process_konfoo_session(ctx, '01SSSSSSSSSSSSSSSSSSSSSSS0', dict(), data, sale_order, 'sale.order.line')

        self.assertEqual(len(sale_order.order_line), 1)

        order_line_0 = sale_order.order_line[0]
        self.assertAlmostEqual(order_line_0.price_unit, 123.0)
        self.assertEqual(order_line_0.product_id.name, 'Initial Name')

        boms_0 = self.env['mrp.bom'].search([('product_tmpl_id', '=', order_line_0.product_id.product_tmpl_id.id)])
        bom_line_ids_0 = boms_0.bom_line_ids.ids
        session_0 = self.env['konfoo.session'].search([('konfoo_session_id', '=', '01SSSSSSSSSSSSSSSSSSSSSSS0')])
        self.assertEqual(len(session_0), 1)
        self.assertEqual(session_0.konfoo_session_id, '01SSSSSSSSSSSSSSSSSSSSSSS0')
        self.assertEqual(order_line_0.product_id.konfoo_session_id.id, session_0.id)
        self.assertEqual(len(boms_0.bom_line_ids), 1)

        data['meta']['name'] = 'Updated Name'
        konfoo.process_konfoo_session(ctx, '01SSSSSSSSSSSSSSSSSSSSSSS1', dict(), data, sale_order, 'sale.order.line')

        self.assertEqual(len(sale_order.order_line), 2)
        self.assertEqual(sale_order.order_line[0].id, order_line_0.id)

        order_line_1 = sale_order.order_line[1]
        self.assertAlmostEqual(order_line_1.price_unit, 123.0)
        self.assertEqual(order_line_1.product_id.name, 'Initial Name')
        self.assertEqual(order_line_0.product_id.name, 'Initial Name')
        self.assertEqual(order_line_0.product_id.id, order_line_1.product_id.id)

        boms_1 = self.env['mrp.bom'].search([('product_tmpl_id', '=', order_line_1.product_id.product_tmpl_id.id)])
        bom_line_ids_1 = boms_1.bom_line_ids.ids
        self.assertEqual(boms_0.ids, boms_1.ids)
        self.assertEqual(len(boms_1.bom_line_ids), 1)
        self.assertEqual(bom_line_ids_0, bom_line_ids_1)  # should be same lines in the bom

        session_1 = self.env['konfoo.session'].search([('konfoo_session_id', '=', '01SSSSSSSSSSSSSSSSSSSSSSS1')])
        self.assertEqual(len(session_1), 1)
        self.assertEqual(session_1.konfoo_session_id, '01SSSSSSSSSSSSSSSSSSSSSSS1')
        self.assertEqual(order_line_1.product_id.konfoo_session_id.id, session_1.id)
        self.assertEqual(order_line_0.product_id.konfoo_session_id.id, session_1.id)
