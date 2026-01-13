from odoo import api, models, fields, _
from odoo.release import version_info
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from os import environ
from urllib.parse import urljoin
from requests.exceptions import RequestException
import types
import json
import requests
import ast
import re

import logging
_logger = logging.getLogger(__name__)


LEGACY_MODEL_FIELD_MAP = {
    'product.product': 'product_id',
    'uom.uom': 'product_uom_id',
    'mrp.workcenter': 'workcenter_id',
}

METADATA_KEYWORDS = (
    'template_product',
    'use_parent_name_prefix',
    'product_name_delimiter',
    'update_if_exists',
    'use_if_exists',
)


def is_production():
    return environ.get('ODOO_STAGE', 'staging') == 'production'


def make_cache_key(rule_id, instance_id):
    return '{}-{}'.format(rule_id, instance_id)

def is_valid_method(model, method):
    return type(getattr(model, method, None)) == types.MethodType

def safe_eval_objects(eval_str, objects_map, instance_id):
    domain_variables = dict()
    for node in ast.walk(ast.parse(eval_str)):
        if not isinstance(node, ast.Name):
            continue
        instance_object = objects_map.get(make_cache_key(node.id, instance_id))
        domain_variables[node.id] = getattr(instance_object, 'id', 0)
    return safe_eval(eval_str, domain_variables)


class KonfooTranslations(object):
    map_translations = None
    default_lang = None
    env = None

    def _validate_translations_map(self):
        installed_langs = [code for code, _ in self.env['res.lang'].get_installed()]
        unavailable_langs = [l for l in self.map_translations.keys() if l not in installed_langs]
        if len(unavailable_langs) > 0:
            raise ValidationError(_(
                'Konfoo translations contain inactive lang. codes "%s"', ', '.join(unavailable_langs)))

        if self.default_lang not in self.map_translations.keys():
            raise ValidationError(_(
                'Konfoo translations must contain company lang. code "%s"', self.default_lang))

    def __init__(self, env, values):
        if not env and not values:
            raise UserError(_('Unable to create object KonfooTranslations'))

        company_lang = env.user.company_id.partner_id.lang
        if isinstance(values, dict):
            translation_values = values
        else:
            translation_values = {company_lang: values}

        self.map_translations = translation_values
        self.default_lang = company_lang
        self.env = env

        self._validate_translations_map()

    def __getitem__(self, key):
        return self.map_translations[key]

    def __setitem__(self, key, value):
        self.map_translations[key] = value
        self._validate_translations_map()

    def update(self, dictionary):
        self.map_translations.update(dictionary)
        self._validate_translations_map()

    def defaults(self):
        return self.default_lang, self.map_translations[self.default_lang]

    def items(self):
        return self.map_translations.items()

    def prefix(self, value):
        for lang, translation in self.map_translations.items():
            self.map_translations[lang] = value + translation if translation else value

    def __str__(self):
        return self.map_translations[self.default_lang]


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

class KonfooLookupSearch(object):
    lookup_model = None
    lookup_domain = None
    lookup_kwargs = None

    def __init__(self, lookup_model, lookup_domain, lookup_kwargs=dict()):
        self.lookup_model = lookup_model
        self.lookup_domain = lookup_domain
        self.lookup_kwargs = lookup_kwargs

    def search(self):
        return self.lookup_model.search(self.lookup_domain, **self.lookup_kwargs)


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

    _logger.info('Fetching BOM data')
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
    def get_parent_model(self):
        konfoo_parent_model = self.env.context.get('konfoo_parent_model')
        if konfoo_parent_model and konfoo_parent_model in self.env:
            return konfoo_parent_model
        return 'sale.order'

    @api.model
    def get_line_model(self):
        konfoo_line_model = self.env.context.get('konfoo_line_model')
        if konfoo_line_model and konfoo_line_model in self.env:
            return konfoo_line_model
        return 'sale.order.line'

    @api.model
    def get_line_lookup_domain(self, line_model, session_id):
        # TODO: optionally we could introduce a parent relationship field (e.g. order_id = parent.id)
        return [('konfoo_session_id', '=', session_id)]

    @api.model
    def get_default_line_options(self):
        return dict(
            quantity='product_uom_qty',
            uom='product_uom',
            product_id='product_id',
            parent_id='order_id',
        )

    @api.model
    def duplicate(self, res_id, konfoo_session_key, parent_model=None, line_model=None):
        ctx = self.configure()
        parent_model, line_model = self._validate_konfoo_models(parent_model, line_model)

        response = requests.post(
            urljoin(ctx.konfoo_url, '/api/v1/state/{}/duplicate'.format(konfoo_session_key)),
            data=json.dumps(dict(key=ctx.konfoo_client_id)))
        if not response:
            raise UserError(_('Could not duplicate session "{}" from Konfoo backend'.format(konfoo_session_key)))
        session_data = response.json()
        if 'id' not in session_data or not session_data['id']:
            raise UserError(_('Duplicated session has no ID'))

        _logger.info('Duplicated session %s as: %s', konfoo_session_key, session_data['id'])
        self.create_from_session(res_id, session_data['id'], parent_model, line_model)

    @api.model
    def create_from_session(self, res_id, session_key, parent_model=None, line_model=None):
        ctx = self.configure()
        parent_model, line_model = self._validate_konfoo_models(parent_model, line_model)

        record = self.env[parent_model].browse([res_id])
        if not record:
            raise UserError(_('Could not find "%s" with id: %s', parent_model, res_id))
        _logger.info('Konfoo updating parent record: %s', record)

        # TODO: find konfoo products on this record and calculate "index" for product name prefix (e.g. S00001/1)

        _logger.info('Fetching configuration state: %s', session_key)
        (session_data, bom_data) = fetch_konfoo_data(ctx.konfoo_url, session_key)

        return self.process_konfoo_session(ctx, session_key, session_data, bom_data, record, line_model)

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

        update_if_exists = meta.get('update_if_exists', False)
        if update_if_exists and not isinstance(update_if_exists, str):
            _logger.warning('Metadata field "update_if_exists" - value should be a field name, found "%s"', update_if_exists)
            update_if_exists = False

        if update_if_exists and update_if_exists not in self.env['product.product']._fields:
            _logger.warning('Metadata field "update_if_exists" - field "%s" does not exist', update_if_exists)
            update_if_exists = False

        use_if_exists = meta.get('use_if_exists', False)
        if use_if_exists and not isinstance(use_if_exists, str):
            _logger.warning('Metadata field "use_if_exists" - value should be a field name, found "%s"', use_if_exists)
            use_if_exists = False

        if use_if_exists and use_if_exists not in self.env['product.product']._fields:
            _logger.warning('Metadata field "use_if_exists" - field "%s" does not exist', use_if_exists)
            use_if_exists = False

        additional_data = meta.copy()
        for keyword in METADATA_KEYWORDS:
            if keyword in additional_data:
                del additional_data[keyword]

        product_name = None
        if 'product_name' in meta:
            product_name = meta['product_name']
            del additional_data['product_name']
        if 'name' in meta:
            product_name = meta['name']
            del additional_data['name']

        product_translations = KonfooTranslations(self.env, product_name)

        if use_parent_name_prefix and parent.name:
            product_translations.prefix(parent.name + product_name_delimiter)

        product_lang, product_name = product_translations.defaults()

        translated_data = dict(name=product_translations)

        for field in list(additional_data.keys()):
            if field.count('.') > 1:
                del additional_data[field]
                _logger.warning('Ignoring metadata field "%s" - using unknown concepts', field)
                continue

            # Handles <ref>.<field> type metadata
            if field.count('.') == 1:
                object_name, field_name = field.strip().split('.')
                value = additional_data[field]
                del additional_data[field]

                if object_name == 'parent':
                    if field_name not in parent._fields:
                        _logger.warning('Ignoring metadata field "%s" - field does not exist in %s', field, parent)
                        continue
                    parent.write({field_name: value})
                elif object_name == 'line':
                    if field_name not in line_model._fields:
                        _logger.warning('Ignoring metadata field "%s" - field does not exist in %s', field, line_model)
                        continue
                    if line is None:
                        _logger.warning('Ignoring metadata field "%s" - `line` values not present', field)
                        continue
                    if line_model is None:
                        _logger.warning('Ignoring metadata field "%s" - `line` data model not present', field)
                        continue
                    line.update({field_name: value})
                else:
                    _logger.warning('Ignoring metadata field "%s" - using unknown object', field)
                continue

            # Handles plain keys (currently constrained to product.product)
            model_field = self.env['product.product']._fields.get(field)
            if not model_field:
                del additional_data[field]
                _logger.warning('Ignoring metadata field "%s" - field does not exist in product.product', field)
                continue
            if model_field and model_field.translate:
                translated_data[model_field.name] = KonfooTranslations(self.env, additional_data[model_field.name])
                del additional_data[model_field.name]

        if update_if_exists and update_if_exists not in additional_data:
            _logger.warning('Metadata field "update_if_exists" - field "%s" does not have value in metadata', update_if_exists)
            update_if_exists = False
        if use_if_exists and use_if_exists not in additional_data:
            _logger.warning('Metadata field "use_if_exists" - field "%s" does not have value in metadata', use_if_exists)
            use_if_exists = False

        options = dict(
            use_parent_name_prefix=use_parent_name_prefix,
            product_name_delimiter=product_name_delimiter,
            update_if_exists=update_if_exists,
            use_if_exists=use_if_exists,
        )

        return template_product, product_name, additional_data, translated_data, options

    @api.model
    def process_konfoo_session(self, ctx, session_key, session_data, bom_data, parent, line_model):
        _logger.info('Creating/updating Konfoo session data: %s', session_key)
        session_object = self._create_or_update_konfoo_session(session_key, session_data, bom_data)

        line_vals = {}

        template_product, product_name, additional_data, translated_data, options = self.process_bom_metadata(
            bom_data, parent,
            line=line_vals,
            line_model=self.env[line_model]
        )

        # Default to product name if not specified by user
        # This does not work together with translated product names
        if version_info[:2] < (16, 0) and 'name' not in line_vals:
            line_vals['name'] = product_name

        _logger.info('Metadata processed - template=%s', template_product)

        (product, created, ignore_rules) = self._konfoo_product(
            ctx, session_object.id, template_product, product_name,
            additional_data=additional_data,
            translated_data=translated_data,
            options=options)

        _logger.info('Using product: %s (id=%s)', product.name, product.id)
        if not ignore_rules:
            bom, created_objects = self.process_aggregated_data(product.product_tmpl_id.id, bom_data, parent=parent)
            _logger.info('Created BOM: %s', bom.id)
            _logger.info('Updating cost')
            product.button_bom_cost()

        if created:
            line_model_options = self.get_default_line_options()
            if getattr(self.env[line_model], 'konfoo_options', None):
                line_model_options = self.env[line_model].konfoo_options()

            if line_model_options.get('quantity'):
                line_vals[line_model_options.get('quantity')] = 1
            if line_model_options.get('uom'):
                line_vals[line_model_options.get('uom')] = ctx.default_uom.id
            if line_model_options.get('product_id'):
                line_vals[line_model_options.get('product_id')] = product.id
            if line_model_options.get('product_template_id'):
                line_vals[line_model_options.get('product_template_id')] = product.product_tmpl_id.id
            if line_model_options.get('parent_id'):
                line_vals[line_model_options.get('parent_id')] = parent.id

            _logger.info('Creating %s: %s', line_model, line_vals)
            line = self.env[line_model].create(line_vals)
            _logger.info('Created: %s', line)
        else:
            line_lookup_domain = self.get_line_lookup_domain(line_model, session_object.id)
            lines = self.env[line_model].search(line_lookup_domain)
            _logger.info('Updating %s: %s', lines, line_vals)
            lines.write(line_vals)
            _logger.info('Updated: %s', lines)

    @api.model
    def process_aggregated_data(self, product_tmpl_id, agg_data, parent=None):
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', product_tmpl_id),
            ('active', '=', True)
        ], limit=1)  # pick first ordered by sequence

        if not bom:
            bom = self.env['mrp.bom'].create({
                'product_tmpl_id': product_tmpl_id,
            })

        allowed_models = self.allowed_models()
        map_cache_objects = dict()
        processed_objects = list()

        for line in agg_data['data']:
            if '__id__' not in line:
                _logger.warning('Received BOM line with no defined __id__: %s', line)
                continue

            if 'model' not in line:
                _logger.warning('Received BOM line with no defined model: %s', line)
                continue

            line_model = line['model']
            if line_model not in allowed_models:
                _logger.warning('Received BOM line with disallowed model: %s', line_model)
                continue

            if parent:
                map_cache_objects[make_cache_key('parent', line.get('__instance__', 'anon'))] = parent

            _logger.info(
                'Executing rule: %s (model=%s, instance=%s)',
                line.get('__id__'), line_model, line.get('__instance__', 'anon'))

            obj = self.process_aggregated_data_line(line, bom.id, map_cache_objects=map_cache_objects)
            processed_objects.append(obj)

        return bom, processed_objects

    @api.model
    def process_aggregated_data_line(self, line, bom_id, map_cache_objects=None):
        additional_data = None
        if line['model'] in ('mrp.bom.line', 'mrp.routing.workcenter'):
            additional_data = dict(bom_id=bom_id)

        model, values, object, method = self.process_agg_line_struct(line, additional_data, map_cache_objects)
        # noinspection PyBroadException
        try:
            res = None
            if method == 'create':
                res = self.create_object(model, values, object)
            elif method == 'read':
                res = object
            elif method == 'write':
                object.write(values)
                res = object
            else:
                res = getattr(object, method)(**values)

            if map_cache_objects is not None:
                map_cache_objects[make_cache_key(line['__id__'], line.get('__instance__', 'anon'))] = res

            return res
        except Exception as err:
            _logger.error(
                'Failed to execute rule: %s (model=%s, instance=%s)',
                line.get('__id__'), line.get('model'), line.get('__instance__', 'anon'))
            _logger.error('Error: %s', err)
            _logger.info('Caused by values/kwargs: %s', values)
            raise UserError(_(
                'Invalid input from rule "%s":\n%s',
                line.get('__id__', _('Unknown')),
                err
            ))

    @api.model
    def process_agg_line_struct(self, data, additional_data=None, map_cache_objects=None):
        reserved = ('__id__', '__instance__', 'model', 'command', 'method', 'records')

        line_instance_id = data.get('__instance__', 'anon')
        line_model = data.get('model')
        if not line_model or line_model not in self.env or line_model not in self.allowed_models():
            raise ValidationError(_('Aggregator line references invalid model: "%s"', line_model))

        line_command = data.get('command', 'create')
        line_method = data.get('method')
        if line_command and line_command not in ['create', 'read', 'write', 'rpc']:
            raise ValidationError(_('Aggregator line references invalid command: "%s"', line_command))
        if line_command == 'rpc' and not (line_method and is_valid_method(self.env[line_model], line_method)):
            raise ValidationError(_('Aggregator line references invalid method: "%s"', line_method))
        elif line_command != 'rpc':
            line_method = line_command

        model_objects = None  # Template for create or recordset for other commands

        line_records = data.get('records')
        if line_records:
            lookup = self.parse_records_search(line_model, line_records, line_instance_id, map_cache_objects)
            if lookup is not None:
                model_objects = lookup.search()
            if not model_objects:
                raise ValidationError(
                    _('Could not find recordset of model "%s" by "%s"',
                      lookup.lookup_model._name, lookup.lookup_domain))

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
                if line_command == 'create' and lookup.target_field == 'template':
                    if not record:
                        raise ValidationError(
                            _('Could not find template object of model "%s" by "%s" = "%s"',
                              lookup.lookup_model, lookup.lookup_field, value))
                    model_objects = record
                else:
                    create[lookup.target_field] = record.id if record else None
                continue

            lookup = self.parse_ref_assignment(key, value, line_instance_id, map_cache_objects)
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
                    _logger.warning('Failed record lookup: %s = %s', field, value)

                create[target_field] = record.id if record else None
                continue

            # All other keys are handled as static
            create[key] = value

        return self.env[line_model], create, model_objects, line_method

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
    def parse_ref_assignment(self, key, value, instance_id, map_cache_objects):
        if not self.is_assignment(key) or not map_cache_objects:
            return None

        target_field, lookup_ref = key.split(':=', 1)
        target_field = target_field.strip()
        lookup_ref = lookup_ref.strip()

        if lookup_ref == 'parent':
            lookup_ref = value
            parent_obj = map_cache_objects.get(make_cache_key('parent', instance_id))
            if parent_obj is not None:
                return KonfooLookupReference(target_field, parent_obj, lookup_ref)

        if '.' in lookup_ref:
            return None

        obj = map_cache_objects.get(make_cache_key(value, instance_id))
        if obj is None:
            return None

        return KonfooLookupReference(target_field, obj, lookup_ref)

    @api.model
    def parse_records_search(self, model, value, instance_id, map_cache_objects):
        if isinstance(value, int):
            return KonfooLookupSearch(self.env[model], [('id', '=', value)])

        # Expected input "(search) [domain] {kwargs}"
        parsed = re.search(r'^(\(search\))(?: )(\[.*?\])(?: )?(\{.*?\})?', str(value))
        if not parsed:
            return None

        (lookup_prefix, lookup_domain, lookup_kwargs) = parsed.groups()
        domain = safe_eval_objects(lookup_domain, map_cache_objects, instance_id)
        kwargs = safe_eval(lookup_kwargs) if lookup_kwargs else dict()

        return KonfooLookupSearch(self.env[model], domain, kwargs)

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
                _logger.info('Konfoo datasets reload: %s', response.text)
            else:
                _logger.warning('Konfoo datasets reload failed: %s', response)
            return bool(response)
        except RequestException as err:
            raise UserError(_('Could not reload remote datasets: %s', str(err)))

    @api.model
    def _main_product_lookup(self, options, additional_data):
        if not options or not additional_data:
            return None

        if options.get('update_if_exists'):
            return self.env['product.product'].search([
                (options.get('update_if_exists'), '=', additional_data.get(options.get('update_if_exists')))
            ], limit=1)

        if options.get('use_if_exists'):
            return self.env['product.product'].search([
                (options.get('use_if_exists'), '=', additional_data.get(options.get('use_if_exists')))
            ], limit=1)

    @api.model
    def _konfoo_product(self, ctx, session_object_id, template_product_value, product_name, additional_data=None, translated_data=None, options=None):
        product = self.env['product.product'].search([('konfoo_session_id', '=', session_object_id)], limit=1)
        create_line = False
        ignore_rules = False

        if not product:
            product = self._main_product_lookup(options, additional_data)
            if product:
                create_line = True
                # the old session gets discarded in this case
                product.write(dict(konfoo_session_id=session_object_id))
                _logger.info('Found existing product: %s (id=%s)', product.name, product.id)

        if product:
            if options.get('use_if_exists'):
                _logger.info('Reusing product: %s (id=%s) - nothing was changed', product.name, product.id)
                ignore_rules = True
            else:
                _logger.info('Reconfiguring product: %s (id=%s)', product.name, product.id)
                vals = dict(name=product_name)
                if additional_data is not None:
                    vals.update(additional_data)
                product.write(vals)
                if translated_data is not None:
                    for field, translations in translated_data.items():
                        for lang, value in translations.items():
                            product.with_context({"lang": lang}).write({field: value})

                if product.bom_count > 0:
                    boms = self.env['mrp.bom'].search([
                        ('product_tmpl_id', '=', product.product_tmpl_id.id), ('active', '=', True)])
                    for existing_bom in boms:
                        _logger.info(
                            f'Archiving copy of existing BOM: {existing_bom} '
                            f'("{product.name or product}", id={product.id})')
                        _archived = existing_bom.copy({
                            'active': False,
                            'code': f'{existing_bom.code} ({_("Deprecated")} {fields.Date.today()})',
                        })
                        existing_bom.bom_line_ids.unlink()
                        existing_bom.operation_ids.unlink()
        else:
            create_line = True
            template_product = self.find_product_by_field(ctx.product_lookup_field, template_product_value)
            if not template_product:
                raise UserError(_('Could not find template product: "{}"'.format(template_product_value)))

            if template_product.bom_count > 0:
                raise UserError(_('Template product should not have BOMs defined'))

            create = dict(name=product_name, konfoo_session_id=session_object_id)
            if additional_data is not None:
                create.update(additional_data)
            product = template_product.copy(create)
            if translated_data is not None:
                for field, translations in translated_data.items():
                    for lang, value in translations.items():
                        product.with_context({"lang": lang}).write({field: value})

        return product, create_line, ignore_rules

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

    @api.model
    def _validate_konfoo_models(self, parent_model, line_model):
        if not parent_model:
            parent_model = self.get_parent_model()
        if not line_model:
            line_model = self.get_line_model()

        if parent_model not in self.env:
            raise UserError(_('Konfoo parent model not found: %s', parent_model))
        if line_model not in self.env:
            raise UserError(_('Konfoo line model not found: %s', line_model))

        return parent_model, line_model
