from odoo.exceptions import ValidationError
from odoo.tests import tagged
from .konfoo_case import KonfooCase
import json


@tagged('-at_install', 'post_install')
class TestKonfooRuleValidate(KonfooCase):

    def _line(self, validate):
        return json.loads("""
            {
                "__id__": "component_product",
                "__instance__": "01VALIDATEAAAAAAAAAAAAAAAA",
                "model": "product.product",
                "name": "Validated product",
                "template := product.product.default_code": "TEMPLATE-VALIDATE",
                "validate": %s
            }
        """ % validate)

    def setUp(self):
        super().setUp()
        self._create_mock_product({
            'name': '[MOCK] Validate template',
            'default_code': 'TEMPLATE-VALIDATE',
        })

    def test_validate_is_reserved(self):
        konfoo = self.konfoo()
        model, create, template_object, method = konfoo.process_agg_line_struct(self._line('true'))
        self.assertNotIn('validate', create)
        self.assertEqual(create['name'], 'Validated product')

    def test_valid_rule_is_created(self):
        konfoo = self.konfoo()
        bom, created_objects = konfoo.process_aggregated_data(
            self.template_product.product_tmpl_id, dict(data=[self._line('true')]), parent=None)
        self.assertEqual(len(created_objects), 1)

    def test_rule_without_validate_is_created(self):
        konfoo = self.konfoo()
        line = self._line('true')
        del line['validate']
        bom, created_objects = konfoo.process_aggregated_data(
            self.template_product.product_tmpl_id, dict(data=[line]), parent=None)
        self.assertEqual(len(created_objects), 1)

    def test_invalid_rule_raises(self):
        konfoo = self.konfoo()
        with self.assertRaises(ValidationError) as ctx:
            konfoo.process_aggregated_data(
                self.template_product.product_tmpl_id, dict(data=[self._line('false')]), parent=None)
        self.assertIn('component_product', str(ctx.exception))
