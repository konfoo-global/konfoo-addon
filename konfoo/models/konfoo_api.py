from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
from os import environ
from urllib.parse import urljoin
from requests.exceptions import RequestException
import json
import requests

import logging
logger = logging.getLogger(__name__)


LEGACY_MODEL_FIELD_MAP = {
    'product.product': 'product_id',
    'uom.uom': 'product_uom_id',
    'mrp.workcenter': 'workcenter_id',
}

METADATA_KEYWORDS = (
    'template_product',
    'use_parent_name_prefix',
    'product_name_delimiter',
)


def is_production():
    return environ.get('ODOO_STAGE', 'staging') == 'production'


def make_cache_key(rule_id, instance_id):
    return '{}-{}'.format(rule_id, instance_id)


class KonfooLookupDom(object):
    target_field = None
    lookup_model = None
    lookup_field = None

    def __init__(self, target_field, lookup_model, lookup_field):
        self.target_field = target_field
        self.lookup_model = lookup_model
        self.lookup_field = lookup_field

    def search(self, value):
        return self.lookup_model.search([(self.lookup_field, '=', value)], limit=1)


class KonfooLookupReference(object):
    target_field = None
    instance = None
    lookup_field = None

    def __init__(self, target_field, instance, lookup_field):
        self.target_field = target_field
        self.instance = instance
        self.lookup_field = lookup_field

    def get(self):
        return self.instance

    def value(self):
        return self.instance[self.lookup_field]


class KonfooContext(object):
    konfoo_url = None
    konfoo_client_id = None
    default_uom = None
    template_product = None
    product_lookup_field = None

    def __init__(self, env=None, company_id=None):
        if not env and not company_id:
            raise UserError(_('Unable to create Konfoo context'))

        company = company_id if company_id else env.user.company_id

        self.konfoo_url = company.konfoo_url if is_production() else company.konfoo_url_staging
        if not self.konfoo_url:
            raise UserError(_('Please configure Konfoo URL in Konfoo settings'))

        self.konfoo_client_id = company.konfoo_client_id if is_production() else company.konfoo_client_id_staging

        self.default_uom = company.konfoo_default_uom_id
        if not self.default_uom:
            raise UserError(_('Please configure Konfoo default unit of measure in Konfoo settings'))

        self.product_lookup_field = company.konfoo_product_lookup_field
        if not self.product_lookup_field:
            self.product_lookup_field = 'default_code'

    def url(self, path):
        return urljoin(self.konfoo_url, path)


def fetch_konfoo_data(konfoo_url, session_key):
    response = requests.get(urljoin(konfoo_url, '/api/v1/state/{}'.format(session_key)))
    if not response:
        raise UserError(_('Could not fetch session "{}" from Konfoo backend'.format(session_key)))
    session_data = response.json()

    logger.info('Fetching BOM data')
    response = requests.get(urljoin(konfoo_url, '/api/v1/agg/bom/{}'.format(session_key)))
    if not response:
        raise UserError(_('Could not fetch BOM for session "{}" from Konfoo backend'.format(session_key)))
    bom_data = response.json()
    return session_data, bom_data


class KonfooAPI(models.AbstractModel):
    _name = 'konfoo.api'
    _description = 'Konfoo API'
    _abstract = True

    @api.model
    def configure(self):
        return KonfooContext(env=self.env)

    @api.model
    def allowed_models(self):
        allowed = {
            'mrp.bom.line',
            'mrp.routing.workcenter',
            'product.product',
            'sale.order.line',
        }

        user_allowed = self.env['konfoo.allowed.model'].search([('company_id', '=', self.env.user.company_id.id)])
        for record in user_allowed:
            allowed.add(record.model)

        return allowed

    @api.model
    def duplicate(self, sale_order_id, konfoo_session_key):
        ctx = self.configure()

        response = requests.post(
            urljoin(ctx.konfoo_url, '/api/v1/state/{}/duplicate'.format(konfoo_session_key)),
            data=json.dumps(dict(key=ctx.konfoo_client_id)))
        if not response:
            raise UserError(_('Could not duplicate session "{}" from Konfoo backend'.format(konfoo_session_key)))
        session_data = response.json()
        if 'id' not in session_data or not session_data['id']:
            raise UserError(_('Duplicated session has no ID'))

        logger.info('Duplicated session %s as: %s', konfoo_session_key, session_data['id'])
        self.create_so_line_from_session(sale_order_id, session_data['id'])

    @api.model
    def create_so_line_from_session(self, sale_order_id, session_key):
        ctx = self.configure()

        sale_order = self.env['sale.order'].browse([sale_order_id])
        if not sale_order:
            raise UserError(_('Could not find "sale.order" with id: {}'.format(sale_order_id)))
        logger.info('Sale order: %s (%s)', sale_order.name, sale_order.id)

        # TODO: find konfoo products on this order and calculate "index" for product name prefix S00001/1

        logger.info('Fetching configuration state')
        (session_data, bom_data) = fetch_konfoo_data(ctx.konfoo_url, session_key)

        return self.process_konfoo_session(ctx, session_key, session_data, bom_data, sale_order)

    @api.model
    def process_bom_metadata(self, bom_data, parent, line=None, line_model=None):
        """
        Example metadata block
        ----------------------

        meta:
            use_parent_name_prefix: true
            product_name_delimiter: " "
            template_product: some-ref

            # this refers to `product.product.name`
            name: (expr) `${odoo['sale.order'].name} Example Product ${root.fields.size}`

            # `parent` refers to `sale.order`
            parent.weight: (expr) root.fields.computed_weight

            # `line` refers to `sale.order.line`
            line.name: (expr) root.fields.computed_product_description
        """

        meta = bom_data.get('meta')
        if not meta:
            raise ValidationError(_('Konfoo BOM data structure contains no metadata block'))

        template_product = meta.get('template_product')
        if not template_product:
            raise ValidationError(_('Konfoo BOM data structure contains no `template_product`'))

        use_parent_name_prefix = bool(meta.get('use_parent_name_prefix', True))
        product_name_delimiter = str(meta.get('product_name_delimiter', ' '))

        additional_data = meta.copy()
        for keyword in METADATA_KEYWORDS:
            if keyword in additional_data:
                del additional_data[keyword]

        product_name_tokens = list()
        if use_parent_name_prefix and parent.name:
            product_name_tokens.append(parent.name)

        if 'product_name' in meta:
            product_name_tokens.append(meta['product_name'])
            del additional_data['product_name']
        if 'name' in meta:
            product_name_tokens.append(meta['name'])
            del additional_data['name']
        product_name = product_name_delimiter.join(product_name_tokens)

        for field in list(additional_data.keys()):
            if field.count('.') > 1:
                del additional_data[field]
                logger.warning('Ignoring metadata field "%s" - using unknown concepts', field)
                continue

            # Handles <ref>.<field> type metadata
            if field.count('.') == 1:
                object_name, field_name = field.strip().split('.')
                value = additional_data[field]
                del additional_data[field]

                if object_name == 'parent':
                    if field_name not in parent._fields:
                        logger.warning('Ignoring metadata field "%s" - field does not exist in %s', field, parent)
                        continue
                    parent.update({field_name: value})
                elif object_name == 'line':
                    if field_name not in line_model._fields:
                        logger.warning('Ignoring metadata field "%s" - field does not exist in %s', field, line_model)
                        continue
                    if line is None:
                        logger.warning('Ignoring metadata field "%s" - `line` values not present', field)
                        continue
                    if line_model is None:
                        logger.warning('Ignoring metadata field "%s" - `line` data model not present', field)
                        continue
                    line.update({field_name: value})
                else:
                    logger.warning('Ignoring metadata field "%s" - using unknown object', field)
                continue

            # Handles plain keys (currently constrained to product.product)
            if field not in self.env['product.product']._fields:
                del additional_data[field]
                logger.warning('Ignoring metadata field "%s" - field does not exist in product.product', field)
                continue

        return template_product, product_name, additional_data

    @api.model
    def process_konfoo_session(self, ctx, session_key, session_data, bom_data, parent):
        logger.info('Creating/updating Konfoo session data: %s', session_key)
        session_object = self._create_or_update_konfoo_session(session_key, session_data, bom_data)

        line_vals = {}

        template_product, product_name, additional_data = self.process_bom_metadata(
            bom_data, parent,
            line=line_vals,
            line_model=self.env['sale.order.line']
        )

        # Default to product name if not specified by user
        if 'name' not in line_vals:
            line_vals['name'] = product_name

        logger.info('Metadata processed - template=%s', template_product)

        (product, created) = self._konfoo_product(
            ctx, session_object.id, template_product, product_name, additional_data=additional_data)

        logger.info('Using product: %s (%s)', product.name, product.id)
        bom, created_objects = self.process_aggregated_data(product.product_tmpl_id.id, bom_data, parent=parent)
        logger.info('Created BOM: %s', bom.id)

        logger.info('Updating cost')
        product.button_bom_cost()

        if created:
            line_vals['product_uom_qty'] = 1
            line_vals['product_uom'] = ctx.default_uom.id
            line_vals['product_id'] = product.id
            line_vals['order_id'] = parent.id
            logger.info('Creating sale.order.line: %s', line_vals)
            self.env['sale.order.line'].create(line_vals)
        else:
            lines = parent.order_line.search([('konfoo_session_id', '=', session_object.id)])
            logger.info('Updating sale.order.line %s: %s', lines, line_vals)
            lines.update(line_vals)

    @api.model
    def process_aggregated_data(self, product_tmpl_id, agg_data, parent=None):
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': product_tmpl_id,
        })

        allowed_models = self.allowed_models()
        map_created_objects = dict()
        created = list()

        for line in agg_data['data']:
            if '__id__' not in line:
                logger.warning('Received BOM line with no defined __id__: %s', line)
                continue

            if 'model' not in line:
                logger.warning('Received BOM line with no defined model: %s', line)
                continue

            line_model = line['model']
            if line_model not in allowed_models:
                logger.warning('Received BOM line disallowed model: %s', line_model)
                continue

            if parent:
                map_created_objects[make_cache_key('parent', line.get('__instance__', 'anon'))] = parent

            logger.info(
                'Executing rule: %s (model=%s, instance=%s)',
                line.get('__id__'), line_model, line.get('__instance__', 'anon'))

            obj = self.process_aggregated_data_line(line, bom.id, map_created_objects=map_created_objects)
            created.append(obj)

        return bom, created

    @api.model
    def process_aggregated_data_line(self, line, bom_id, map_created_objects=None):
        additional_data = None
        if line['model'] in ('mrp.bom.line', 'mrp.routing.workcenter'):
            additional_data = dict(bom_id=bom_id)

        model, create, template_object = self.process_agg_line_struct(line, additional_data, map_created_objects)
        # noinspection PyBroadException
        try:
            obj = self.create_object(model, create, template_object)
            if map_created_objects is not None:
                map_created_objects[make_cache_key(line['__id__'], line.get('__instance__', 'anon'))] = obj
            return obj
        except Exception as err:
            logger.error(
                'Failed to create object from rule: %s (model=%s, instance=%s)',
                line.get('__id__'), line.get('model'), line.get('__instance__', 'anon'))
            logger.error('Error: %s', err)
            logger.info('Caused by this create object: %s', create)
            raise UserError(_(
                'Konfoo encountered invalid input from rule %s\n%s',
                line.get('__id__', _('Unknown')),
                err
            ))

    @api.model
    def process_agg_line_struct(self, data, additional_data=None, map_created_objects=None):
        reserved = ('__id__', '__instance__', 'model')

        line_instance_id = data.get('__instance__', 'anon')
        line_model = data.get('model')
        if not line_model or line_model not in self.env or line_model not in self.allowed_models():
            raise ValidationError(_('Aggregator line references invalid model: "%s"', line_model))

        template_object = None
        create = dict()
        if additional_data and isinstance(additional_data, dict):
            create.update(additional_data)

        for key, value in data.items():
            if key in reserved or key in create:
                continue

            lookup = self.parse_assignment(key)
            if lookup is not None:
                if lookup.target_field in reserved:
                    continue

                record = lookup.search(value)
                if lookup.target_field == 'template':
                    if not record:
                        raise ValidationError(
                            _('Could not find template object of model "%s" by "%s" = "%s"',
                              lookup.lookup_model, lookup.lookup_field, value))
                    template_object = record
                else:
                    create[lookup.target_field] = record.id if record else None
                continue

            lookup = self.parse_ref_assignment(key, value, line_instance_id, map_created_objects)
            if lookup is not None:
                if lookup.target_field in reserved:
                    continue
                create[lookup.target_field] = lookup.value()
                continue

            # legacy lookup support (konfoo <= 0.4.0)
            model, field = self.parse_odoo_ref(key)
            if model and field and model in LEGACY_MODEL_FIELD_MAP:
                target_field = LEGACY_MODEL_FIELD_MAP[model]
                if target_field in create:
                    continue
                record = self.env[model].search([(field, '=', value)], limit=1)
                if not record:
                    logger.warning('Failed record lookup: %s = %s', field, value)

                create[target_field] = record.id if record else None
                continue

            # All other keys are handled as static
            create[key] = value

        return self.env[line_model], create, template_object

    @api.model
    def create_object(self, model, create, template_object=None):
        if template_object:
            return template_object.with_context({'lang': 'en_US'}).copy(create)
        return model.create(create)

    @api.model
    def parse_odoo_ref(self, key):
        if '.' not in key:
            return None, None
        idx = key.rindex('.')
        model = key[:idx].strip()
        field = key[idx + 1:].strip()
        if not model or not field:
            return None, None
        if model not in self.env:
            return None, None
        return model, field

    @api.model
    def is_assignment(self, key):
        return key.count(':=') == 1

    @api.model
    def parse_assignment(self, key):
        if not self.is_assignment(key):
            return None

        target_field, lookup_ref = key.split(':=', 1)
        target_field = target_field.strip()
        lookup_ref = lookup_ref.strip()

        lookup_model, lookup_field = self.parse_odoo_ref(lookup_ref)
        if not lookup_model or not lookup_field:
            return None

        return KonfooLookupDom(target_field, self.env[lookup_model], lookup_field)

    @api.model
    def parse_ref_assignment(self, key, value, instance_id, map_created_objects):
        if not self.is_assignment(key) or not map_created_objects:
            return None

        target_field, lookup_ref = key.split(':=', 1)
        target_field = target_field.strip()
        lookup_ref = lookup_ref.strip()

        if lookup_ref == 'parent':
            lookup_ref = value
            parent_obj = map_created_objects.get(make_cache_key('parent', instance_id))
            if parent_obj is not None:
                return KonfooLookupReference(target_field, parent_obj, lookup_ref)

        if '.' in lookup_ref:
            return None

        obj = map_created_objects.get(make_cache_key(value, instance_id))
        if obj is None:
            return None

        return KonfooLookupReference(target_field, obj, lookup_ref)

    @api.model
    def find_product_by_field(self, field, value):
        return self.env['product.product'].search([(field, '=', value)], limit=1)

    @api.model
    def find_uom_by_field(self, field, value):
        return self.env['uom.uom'].search([(field, '=', value)], limit=1)

    @api.model
    def dataset_reset(self, name, fields):
        url = urljoin(self._get_sponge_url(), name)
        headers = {'x-api-key': self._get_sponge_key()}
        data = dict(fields=['id'] + fields)
        try:
            response = requests.put(url, headers=headers, json=data)
            if not response:
                raise UserError(_('Could not reset dataset: %s', name))
        except RequestException as err:
            raise UserError(_('Could not reset dataset: %s - %s', name, str(err)))

    @api.model
    def dataset_set_indices(self, name, indices):
        url = urljoin(self._get_sponge_url(), f'{name}/index')
        headers = {'x-api-key': self._get_sponge_key()}
        try:
            response = requests.put(url, headers=headers, json=indices)
            if not response:
                raise UserError(_('Could not set dataset indices: %s', name))
        except RequestException as err:
            raise UserError(_('Could not set dataset indices: %s - %s', name, str(err)))

    @api.model
    def dataset_patch_data(self, name, data):
        url = urljoin(self._get_sponge_url(), name)
        headers = {'x-api-key': self._get_sponge_key()}
        try:
            response = requests.patch(url, headers=headers, json=data)
            return bool(response)
        except RequestException as err:
            raise UserError(_('Could not update dataset: %s - %s', name, str(err)))

    @api.model
    def reload_datasets(self):
        url = urljoin(self._get_konfoo_url(), '/api/v1/admin/datasets-reload')
        headers = {'x-api-key': self._get_sponge_key()}
        try:
            response = requests.get(url, headers=headers)
            if response:
                logger.info('Konfoo datasets reload: %s', response.text)
            else:
                logger.warning('Konfoo datasets reload failed: %s', response)
            return bool(response)
        except RequestException as err:
            raise UserError(_('Could not reload remote datasets: %s', str(err)))

    @api.model
    def _konfoo_product(self, ctx, session_object_id, template_product_value, product_name, additional_data=None):
        product = self.env['product.product'].search([('konfoo_session_id', '=', session_object_id)], limit=1)
        if product:
            logger.info('Reconfiguring product: %s (%s)', product.name, product.id)
            vals = dict(name=product_name)
            if additional_data is not None:
                vals.update(additional_data)
            product.update(vals)
            if product.bom_count > 0:
                logger.info('Removing existing BOMs from the product %s', product)
                boms = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.product_tmpl_id.id)])
                logger.info('Found BOMs: %s', boms)
                boms.unlink()
            return product, False

        template_product = self.find_product_by_field(ctx.product_lookup_field, template_product_value)
        if not template_product:
            raise UserError(_('Could not find template product: "{}"'.format(template_product_value)))

        if template_product.bom_count > 0:
            raise UserError(_('Template product should not have BOMs defined'))

        create = dict(name=product_name, konfoo_session_id=session_object_id)
        if additional_data is not None:
            create.update(additional_data)
        product = template_product.with_context({'lang': 'en_US'}).copy(create)
        return product, True

    @api.model
    def _create_or_update_konfoo_session(self, session_id, session_data, bom_data):
        json_session = json.dumps(session_data)
        json_bom = json.dumps(bom_data)
        session = self.env['konfoo.session'].search([('konfoo_session_id', '=', session_id)], limit=1)
        if session:
            session.write({
                'konfoo_object': json_session,
                'konfoo_bom': json_bom,
            })
            return session
        else:
            return self.env['konfoo.session'].create({
                'konfoo_session_id': session_id,
                'konfoo_object': json_session,
                'konfoo_bom': json_bom,
            })

    @api.model
    def _get_sponge_url(self):
        company = self.env.user.company_id
        url = company.konfoo_sync_host if is_production() else company.konfoo_sync_host_staging
        if not url:
            raise UserError(_('Konfoo sync host is not configured'))
        return url

    @api.model
    def _get_sponge_key(self):
        company = self.env.user.company_id
        key = company.konfoo_sync_key if is_production() else company.konfoo_sync_key_staging
        if not key:
            raise UserError(_('Konfoo sync key is not configured'))
        return key

    @api.model
    def _get_konfoo_url(self):
        company = self.env.user.company_id
        url = company.konfoo_url if is_production() else company.konfoo_url_staging
        if not url:
            raise UserError(_('Konfoo URL is not configured'))
        return url
