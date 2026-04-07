from odoo.tests import TransactionCase, tagged, Form
from odoo.release import version_info

import logging
logger = logging.getLogger(__name__)



@tagged('-at_install', 'post_install')
class KonfooCase(TransactionCase):

    def _create_mock_product(self, values):
        if version_info[:2] < (18, 0):
            values['type'] = 'product'
        else:
            values['is_storable'] = True
        return self.env['product.product'].create(values)

    def setUp(self):
        super().setUp()

        self.company = self.env.user.company_id

        # NOTE: the values do not matter because we avoid doing any requests
        self.company.konfoo_url = self.company.konfoo_url_staging = 'http://localhost:8000'
        self.company.konfoo_client_id_staging = self.company.konfoo_client_id = 'test'
        self.company.konfoo_default_uom_id = self.env.ref('uom.product_uom_unit').id

        self.template_product = self._create_mock_product({
            'name': '[MOCK] Product Template',
            'default_code': 'KONFOO-TEMPLATE'
        })

        self.product = self._create_mock_product({
            'name': '[MOCK] Mock Product',
            'default_code': 'TEST'
        })

        customer = Form(self.env['res.partner'])
        customer.name = '[MOCK] Customer'

        (MAJOR, _, _, _, _, _THIS_NOT_IN_THE_FORMAT_SPEC) = version_info
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

    def konfoo(self):
        konfoo = self.env['konfoo.api']
        self.assertIsNotNone(konfoo)
        return konfoo
