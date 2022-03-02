# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class payment_transaction(models.Model):
    _inherit = 'payment.transaction'

    mp_response = fields.Html( string="mercadopago")
    mp_json_response = fields.Text( string="JSON MP Response")