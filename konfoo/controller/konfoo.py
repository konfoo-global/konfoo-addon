from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo.release import version_info

import logging
logger = logging.getLogger(__name__)

JSON_CONTROLLER_TYPE = 'jsonrpc'
if version_info[:2] <= (18, 0):
    JSON_CONTROLLER_TYPE = 'json'

class KonfooController(http.Controller):
    @http.route('/konfoo/create', type=JSON_CONTROLLER_TYPE, auth='user')
    def create(self, sale_order_id, session):
        konfoo_api = request.env['konfoo.api']
        konfoo_api.create_so_line_from_session(sale_order_id, session)

    @http.route('/konfoo-client', type=JSON_CONTROLLER_TYPE, auth='user')
    def get_client_params(self):
        konfoo_api = request.env['konfoo.api']
        try:
            ctx = konfoo_api.configure()
            return dict(ok=True, url=ctx.konfoo_url, client_id=ctx.konfoo_client_id)
        except UserError as err:
            logger.warning(err)
            return dict(ok=False, error=str(err))
