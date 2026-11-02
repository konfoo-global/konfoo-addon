from odoo.tests import tagged
from .konfoo_case import KonfooCase


@tagged('-at_install', 'post_install')
class TestKonfooDatasetDelete(KonfooCase):

    def test_delete_dataset_removes_fields_and_cache(self):
        dataset = self.env['konfoo.dataset'].create({
            'name': 'DELETE-ME',
            'model_id': 'product.product',
        })
        self.env['konfoo.dataset_field'].create({
            'dataset_id': dataset.id,
            'name': 'name',
            'csv_name': 'name',
            'is_unique': False,
            'is_group': False,
        })
        self.env['konfoo.dataset_object'].create({
            'dataset_id': dataset.id,
            'res_id': self.product.id,
            'sync_date': '2026-01-01 00:00:00',
        })

        dataset.unlink()

        fields_left = self.env['konfoo.dataset_field'].search_count([('dataset_id', '=', dataset.id)])
        cache_left = self.env['konfoo.dataset_object'].search_count([('dataset_id', '=', dataset.id)])
        self.assertEqual(fields_left, 0)
        self.assertEqual(cache_left, 0)
