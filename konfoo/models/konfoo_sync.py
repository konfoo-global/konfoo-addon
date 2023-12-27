from odoo import models, api
import time
import logging

logger = logging.getLogger(__name__)


def get_cron_time_limit():
    from odoo.tools import config
    limit_time_real_cron = config['limit_time_real_cron']
    if limit_time_real_cron <= 0:
        limit_time_real_cron = 900  # limit to odoo.sh default for the time being
    return limit_time_real_cron


class KonfooSync(models.AbstractModel):
    _name = 'konfoo.sync'
    _description = 'Konfoo Data Sync'

    @api.model
    def cron_push_datasets(self):
        limit_time = get_cron_time_limit()
        start = time.time()
        logger.info('Konfoo data synchronization start (limit=%ss)', limit_time)

        def check_limit():
            if limit_time > 0 and time.time() - start > limit_time - 60:
                logger.warning('Reached close to thread time limit (%ss), continuing next interval', limit_time)
                raise StopIteration()

        datasets = self.env['konfoo.dataset'].search([('active', '=', True)])
        num_records = 0
        for dataset in datasets:
            num_records += dataset.sync_dataset(check_limit=check_limit)
        logger.info('Synchronized %s records', num_records)

        self.env['konfoo.api'].reload_datasets()

    @api.model
    def sync_records(self, dataset, records):
        konfoo = self.env['konfoo.api']
        if not konfoo.dataset_patch_data(dataset.name, records):
            logger.warning('Dataset update failed: %s', dataset.name)
            return 0

        query = """
        INSERT INTO konfoo_dataset_object (dataset_id, res_id, sync_date)
        VALUES (%s, %s, NOW())
        ON CONFLICT (dataset_id, res_id) DO UPDATE SET sync_date = NOW()
        """
        for record in records:
            self.env.cr.execute(query, (dataset.id, record.get('id')))
        return len(records)
