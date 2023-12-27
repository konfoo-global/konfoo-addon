from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import expression
from odoo.tools.safe_eval import safe_eval, datetime
import re
import time

from .konfoo_sync import get_cron_time_limit

import logging
logger = logging.getLogger(__name__)

DATASET_NAME_VALIDATOR = re.compile(r'[^a-zA-Z0-9\-]')


def valid_dataset_name(name):
    if not name or len(name) == 0:
        raise ValidationError(_('Dataset name cannot be empty'))
    if name[0].isdigit():
        raise ValidationError(_('Dataset name cannot start with a digit'))
    if bool(DATASET_NAME_VALIDATOR.search(name)):
        raise ValidationError(_('Dataset name can only contain ASCII characters in range A..Z and digits (0..9)'))
    return True


class KonfooDataset(models.Model):
    _name = 'konfoo.dataset'
    _description = 'Konfoo Dataset'
    _sql_constraints = [
        ('uniq_name', 'unique(name)', "Dataset names must be unique"),
    ]

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company, required=True)
    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active', required=True, default=True)
    model_id = fields.Selection(selection='_list_all_models', string='Model', required=True)
    domain = fields.Text(default='[]', required=True)

    fields = fields.One2many(
        'konfoo.dataset_field', 'dataset_id', string='Fields', copy=True, auto_join=True)

    @api.model
    def _list_all_models(self):
        # TODO: handle translatable model name properly
        self._cr.execute("SELECT model, model FROM ir_model ORDER BY model")
        options = self._cr.fetchall()
        return options

    @api.constrains('name')
    def _check_name(self):
        """
        Only allow names that:
            * matches!(c, '0'..='9' | 'A'..='Z' | 'a'..='z' | '-')
            * do not start with a digit
        """
        for record in self:
            valid_dataset_name(record.name)

    @api.constrains('model_id')
    def _check_model(self):
        for record in self:
            logger.info('Model changed: %s', record.name)
            record.fields.unlink()
            record.reset_dataset()

    def action_sync_now(self):
        limit_time = get_cron_time_limit()
        start = time.time()
        logger.info('On demand Konfoo data synchronization start (limit=%ss)', limit_time)

        def check_limit():
            if limit_time > 0 and time.time() - start > limit_time - 60:
                logger.warning('Reached close to thread time limit (%ss), continuing next interval', limit_time)
                raise StopIteration()

        num_records = 0
        for record in self:
            num_records += record.sync_dataset(check_limit=check_limit)
        logger.info('Synchronized %s records', num_records)

        self.env['konfoo.api'].reload_datasets()

    def action_reset_dataset(self):
        self.reset_dataset()

    @api.constrains('name', 'fields')
    def reset_dataset(self):
        konfoo = self.env['konfoo.api']
        for record in self:
            if len(record.fields) == 0:
                continue
            logger.info('Vital information changed - resetting dataset: %s', record.name)
            self.env['konfoo.dataset_object'].search([('dataset_id', '=', record.id)]).unlink()
            konfoo.dataset_reset(record.name, [field.csv_name for field in record.fields])
            konfoo.dataset_set_indices(record.name, record.get_indices())

    def sync_dataset(self, check_limit=None):
        self.ensure_one()

        if not self.active or len(self.fields) == 0:
            return 0

        changes = self.detect_changes()
        if len(changes) == 0:
            return 0

        logger.info('Dataset: %s (%s) - %s changed records', self.name, self.model_id, len(changes))

        konfoo_sync = self.env['konfoo.sync']
        max_batch_size = self.company_id.konfoo_sync_batch_size or 100
        num_records = 0
        model = self.get_model()
        records = model.browse(changes)
        batch = list()
        try:
            for record in records:
                if len(batch) == max_batch_size:
                    num_records += konfoo_sync.sync_records(self, batch)
                    batch = list()

                    if check_limit is not None:
                        check_limit()

                serialized = self.serialize_record(record)
                batch.append(serialized)

            if len(batch) > 0:
                num_records += konfoo_sync.sync_records(self, batch)

            if check_limit is not None:
                check_limit()
        except StopIteration:
            pass
        return num_records

    def get_domain(self):
        self.ensure_one()
        return safe_eval(self.domain, {
            'datetime': datetime,
            'context_today': datetime.datetime.now,
        })

    def get_model(self):
        self.ensure_one()
        return self.env[self.model_id]

    def get_indices(self):
        self.ensure_one()
        indices = [dict(index_type='UNIQUE', name='id', column='id')]
        for field in self.fields:
            if field.is_unique:
                indices.append(dict(index_type='UNIQUE', name=field.name, column=field.csv_name))
            if field.is_group:
                indices.append(dict(index_type='GROUP', name=field.name, column=field.csv_name))
        return indices

    def detect_changes(self):
        self.ensure_one()
        domain = self.get_domain()
        logger.info('Detecting changes on %s: %s', self.name, domain)

        expr = expression(domain, self.env[self.model_id])
        table, where, params = expr.query.get_sql()
        model_table_name = self.env[self.model_id]._table

        query = f"""
        select "{model_table_name}"."id" from {table}
        left join konfoo_dataset_object cache
        on "{model_table_name}"."id" = cache.res_id and cache.dataset_id = {self.id}
        where {where}
        and (cache.sync_date < "{model_table_name}"."write_date" or cache.sync_date is null)
        """

        self.env.cr.execute(query, params)
        return list(map(lambda x: x[0], self.env.cr.fetchall()))

    def get_serialize_fields(self):
        self.ensure_one()
        return [('id', 'id')] + [(field.name, field.csv_name) for field in self.fields]

    def serialize_record(self, record):
        self.ensure_one()
        data = dict()
        for (field, csv_name) in self.get_serialize_fields():
            data[csv_name] = record[field]
        return data

    def get_serialized_fast(self, ids):
        # TODO: properly support related fields
        # TODO: remove compute fields

        self.ensure_one()

        expr = expression([('id', 'in', ids)], self.env[self.model_id])
        model = self.get_model()
        columns = list()
        for field in self.fields:
            res = model._inherits_join_calc(model._table, field.name, expr.query)
            columns.append(f'{res} as "{field.csv_name}"')

        (query, params) = expr.query.select(*columns)
        logger.info('query: %s', query)
        logger.info('params: %s', params)
        sql = f'SELECT to_json(r) FROM ({query}) r'
        self.env.cr.execute(sql, params)
        results = list(map(lambda x: x[0], self.env.cr.fetchall()))
        logger.info(results)
        return results

