# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from werkzeug import urls
import os, hashlib, decimal, datetime, re, json, math, sys
import mercadopago
import werkzeug
import time
import logging
_logger = logging.getLogger(__name__)

class mercadopago_controller(http.Controller):

    formsPath = str(os.path.dirname(os.path.abspath(__file__))).replace("controllers","")
    default_documents_types = {"CO":"CC","AR":"DNI","BR":"CPF","CL":"RUT","PE":"DNI","UY":"CI","MX":"RFC"}

    @http.route('/mercadopago/get_mercadopago_acquirer/', methods=['POST'], type='json', auth="public", website=True)
    def get_mercadopago_acquirer(self, **kw):       
        response = {"acquirer":None,"form_bill":None}                
        query = "select id, name, website_id,company_id, state, provider, mp_service_mode, mp_client_id, mp_public_key, mp_country from payment_acquirer where provider = 'mercadopago' limit 1"
        request.cr.execute(query)    
        acquirer = request.cr.dictfetchone()

        if(acquirer['mp_service_mode']=="basic"):
            response = {"acquirer":acquirer,'bill_form': self.file_get_contents(str(self.formsPath)+str("/static/src/form/bill.html")), }
        else: # custom one
            response = {"acquirer":acquirer,'bill_form': self.file_get_contents(str(self.formsPath)+str("/static/src/form/bill_custom.html")), }

        return response
        
    @http.route('/mercadopago/get_sale_order/', methods=['POST'], type='json', auth="public", website=True)
    def get_sale_order(self, **kw): 
        params = {}
        params['acquirer_id'] = kw.get('acquirer_id')
        params['partner_id'] = kw.get('partner_id')
                       
        query = "select name, website_id,company_id, state, provider, mp_service_mode, mp_client_id, mp_client_secret, mp_public_key, mp_access_token, mp_country from payment_acquirer where provider = 'mercadopago' limit 1"
        
        request.cr.execute(query)
        acquirer = request.cr.dictfetchone()
         
        if(acquirer['state']=="test"):
            state = str('1')
        else:
            state = str('0')

        query = "select id, name, amount_total, amount_tax, date_order, partner_shipping_id from sale_order where partner_id = '"+str(params['partner_id'])+"' and state = '"+str('draft')+"' order by date_order desc limit 1"
        
        request.cr.execute(query)    
        draft_order = request.cr.dictfetchone()                   
       
        query = "select res_partner.id, res_partner.name, res_partner.vat, res_partner.phone, res_partner.mobile, res_partner.email, res_partner.street, res_partner.city, res_partner.zip, res_partner.lang, res_country.name as country_name, res_country.code as country_code, res_country_state.name as state_name, res_currency.name as currency_name, res_currency.symbol as currency_symbol from res_partner left join res_country on res_country.id = res_partner.country_id left join res_country_state on res_country_state.id = res_partner.state_id left join res_currency on res_country.currency_id = res_currency.id   where res_partner.id = '"+str(draft_order['partner_shipping_id'])+"' limit 1"
        
        request.cr.execute(query)    
        res_partner_shipping = request.cr.dictfetchone()

        if(draft_order):                                   
            order_name = str(datetime.datetime.now())
            order_name = re.sub('[^0-9]','', order_name)
            order_name = order_name[-9:]

            # base url
            query = "select value from ir_config_parameter where key = 'web.base.url' limit 1"
            request.cr.execute(query)
            ir_config_parameter = request.cr.dictfetchone()
            base_url = ir_config_parameter['value']

            draft_order_lines = http.request.env['sale.order.line'].sudo().search([['order_id','=',draft_order["id"]]])   
            checkout_items = []
            checkout_taxes = []
             
            query = "select show_line_subtotals_tax_selection from res_config_settings where company_id = " + str(request.website.company_id.id)
            request.cr.execute(query)
            setting = request.cr.dictfetchone()

            if(setting):
                pass
            else:
                setting = {}
                setting['show_line_subtotals_tax_selection'] = 'tax_included'

            
            for order_line in draft_order_lines:
                unit_price = float(0.0)
                
                if(setting):
                    if(setting['show_line_subtotals_tax_selection'] == 'tax_excluded'):
                        if(order_line.currency_id.name=="COP"):
                            unit_price = int(math.ceil(((float(order_line.price_unit) + (float(order_line.price_tax) / float(order_line.product_uom_qty))))))
                        else:
                            unit_price = ((float(order_line.price_unit) + (float(order_line.price_tax) / float(order_line.product_uom_qty)))) # / float(order_line.product_uom_qty)
                            unit_price_parted = str(unit_price).split(".")
                            if(unit_price_parted[1]=="0"):
                                unit_price = unit_price + float(0.01)
                    else:
                        if(order_line.currency_id.name=="COP"):
                            unit_price = int(math.ceil(float(order_line.price_total) / float(order_line.product_uom_qty)))
                        else:
                            unit_price = float(order_line.price_total) / float(order_line.product_uom_qty)
                            unit_price_parted = str(unit_price).split(".")
                            if(unit_price_parted[1]=="0"):
                                unit_price = unit_price + float(0.01)
                        
                checkout_item = {
                                    "title":order_line.name,
                                    "quantity":order_line.product_uom_qty,
                                    "currency_id":order_line.currency_id.name,
                                    "unit_price":unit_price                                    
                                }

                if(float(checkout_item['unit_price'])>0):
                    checkout_items.append(checkout_item)
                
                    query = "select tax_id from product_taxes_rel where prod_id = " + str(order_line.product_id.id)
                    request.cr.execute(query)
                    product_taxes = request.cr.dictfetchall()

                    if(setting):
                        if(setting['show_line_subtotals_tax_selection'] != 'tax_excluded'):
                            for product_tax in product_taxes:
                                taxes_details = http.request.env['account.tax'].sudo().search([['id','=',product_tax['tax_id']]])  
                                if('IVA' in str(taxes_details.name) and 'INC' in str(taxes_details.name)):
                                    if(int(taxes_details.amount)>0):
                                        tax = {
                                                "type":"IVA",
                                                "value":int(taxes_details.amount)
                                              }
                                        if(checkout_taxes.__len__()>0):
                                            for tax_added in checkout_taxes:                            
                                                if(int(tax_added["value"])!=int(taxes_details.amount)):
                                                    checkout_taxes.append(tax)
                                        else:
                                            checkout_taxes.append(tax)
            
            jsonPreference = str("")
            if('mp_service_mode' in acquirer):
                mp = mercadopago.MP(acquirer['mp_client_id'], acquirer['mp_client_secret'])
                if(state=="1"):
                    mp.sandbox_mode(True)
                else:
                    mp.sandbox_mode(False)

                preference =   {
                                    "items": checkout_items
                               }                                

                if(checkout_taxes.__len__()>0):
                    preference['taxes'] = checkout_taxes
                
                if(res_partner_shipping['name']!=""):
                    payer = {
                                "name": res_partner_shipping['name'],
                                "email": res_partner_shipping['email'],
                                "phone": {
                                            "number": res_partner_shipping['phone'] if res_partner_shipping['phone']!="" else res_partner_shipping['mobile']
                                        },
                                "identification":  {
                                                        "type": self.default_documents_types[""+res_partner_shipping['country_code']+""],
                                                        "number": res_partner_shipping['vat']
                                                    },
                                "address": {
                                                "street_name": res_partner_shipping['street'],
                                                "zip_code": res_partner_shipping['zip']
                                            }
                            }
                    preference['payer'] = payer

                    shipments = {
                                    "receiver_address": {
                                                            "zip_code": res_partner_shipping['zip'],
                                                            "street_name": res_partner_shipping['street']
                                                        }
                                }
                    preference['shipments'] = shipments
                
                back_urls = {
                                "success": urls.url_join(base_url, '/shop/process_mercadopago_payment'),
                                "pending": urls.url_join(base_url, '/shop/process_mercadopago_payment'),
                                "failure": urls.url_join(base_url, '/shop/process_mercadopago_payment')
                            }
                            
                preference['back_urls'] = back_urls
                preference['auto_return'] = "approved"
                preference['external_reference'] = draft_order['id']           
                     
                preferenceResult = mp.create_preference(preference)

                jsonPreference = json.dumps(preferenceResult)
                
                draft_order = request.env['sale.order'].sudo().browse(draft_order['id'])
                draft_order.sudo().update({'last_collector_id': draft_order['id']})
                
                if(acquirer['mp_service_mode']=="basic"):
                    return {
                            'status': "OK",
                            'state': state,                        
                            'json_preference': jsonPreference,
                            'checkout_items': checkout_items
                            }
                else:
                    return {
                            'status': "OK",
                            'state': state,                        
                            'json_preference': preference,
                            'checkout_items': checkout_items
                            }
            

    @http.route('/shop/process_mercadopago_payment', csrf=False, auth="public", website=True)    
    def process_mercadopago_payment(self, **kw):
        _response = {}
       
        _response['collection_id'] = kw.get('collection_id')
        _response['collection_status'] = kw.get('collection_status')
        _response['external_reference'] = kw.get('external_reference')
        _response['payment_type'] = kw.get('payment_type')
        _response['merchant_order_id'] = kw.get('merchant_order_id')
        _response['preference_id'] = kw.get('preference_id')
        _response['site_id'] = kw.get('site_id')
        _response['processing_mode'] = kw.get('processing_mode')
        _response['merchant_account_id'] = kw.get('merchant_account_id')
        
        try:
            _response_html = self._mercadopago_reponse_formatter(_response)
            if(_response['collection_status']==str("pending") 
                or _response['collection_status']==str("success") 
                or _response['collection_status']==str("failure") 
                or _response['collection_status']==str("approved")
                or _response['collection_status']==str("rejected")
                or _response['collection_status']==str("in_process")):

                if(_response['collection_status']==str("failure") or _response['collection_status']==str("rejected")):
                    return werkzeug.utils.redirect("/shop/payment?state=fail")
                
                if(int(_response['external_reference'])>0):

                    current_sale_order_id = int(_response['external_reference'])
                    sale_order = http.request.env['sale.order'].sudo().search([['id','=',current_sale_order_id]], limit=1)
                    query = "select id from payment_acquirer where provider = 'mercadopago' limit 1"
                    request.cr.execute(query)
                    acquirer = request.cr.dictfetchone()
                    acquirer_id = False
                    if(acquirer['id']):
                        acquirer_id = acquirer['id']   

                        if(request.session.uid!=None):
                                sale_order.sudo().write({'user_id':request.session.uid})                                                                                                                                                                    

                        if(_response['collection_status']==str("success") 
                            or _response['collection_status']==str("approved")
                            or _response['collection_status']==str("pending")
                            or _response['collection_status']==str("in_process")):                            

                            if(_response['collection_status'] == str("pending") or _response['collection_status'] == str("in_process") or _response['collection_status'] == str("approved")):
                                request.website.sale_reset()
                                request.env['payment.acquirer'].sudo().mercadopago_sync_orders_payments(current_sale_order_id)
                                
                        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                        url_send = str(base_url) + str("/shop/payment")
                        uid = http.request.env.context.get('uid')
                        sale_order = http.request.env['sale.order'].sudo().browse(int(current_sale_order_id))
                        sharable = sale_order._get_share_url(redirect=True)
                        url_sharable = str(base_url) + str(sharable)
                        
                        if(sale_order):
                            if(sale_order.state != "draft"):
                                if (not uid):
                                    url_send = url_sharable
                                else:
                                    if(sale_order.require_payment):
                                        url_send = url_sharable
                                    else:
                                        url_send = url_sharable
                        else:
                           return werkzeug.utils.redirect("/shop/payment") 
                        return werkzeug.utils.redirect(url_send)
                else:
                    return werkzeug.utils.redirect("/shop/payment")

            else:
                return werkzeug.utils.redirect("/shop/payment")

        except Exception as e:
            exc_traceback = sys.exc_info()
            return werkzeug.utils.redirect("/shop/payment")
    
    def file_get_contents(self, filename):
        with open(filename) as f:
            return f.read()

    def file_put_contents(self, filename,data):
        with open(filename,'w') as f:
            return f.write(data)
    
    def _mercadopago_reponse_formatter(self, _response):

        _statusText = {
                        "null":"",
                        "pending":"Transacción pendiente o en validación",
                        "success":"Transacción aprobada",
                        "approved":"Transacción aprobada",
                        "failure":"Transacción expirada",
                        "rejected":"Transacción rechazada",
                        "in_process":"Transacción en proceso",
                      }
        _ml_sites = {
                        "MCO":["Colombia",['credit_card','ticket','bank_transfer','account_money']],
                        "MLA":["Argentina",['credit_card','debit_card','ticket','atm','account_money']],
                        "MLC":["Chile",['credit_card','ticket','bank_transfer','account_money']],
                        "MLB":["Brasil",['credit_card','ticket','digital_currency','account_money']],
                        "MLM":["México",['credit_card','debit_card','prepaid_card','ticket','atm','account_money','digital_currency']],
                        "MLU":["Uruguay",['credit_card','atm','account_money']],
                        "MPE":["Perú",['credit_card','debit_card','atm','account_money']],
                    }
        _ml_payment_types = {
                                'credit_card':'Tarjeta Crédito',
                                'debit_card':'Tarjeta Débito',
                                'ticket':'Ticket',
                                'bank_transfer':'Transferencia Bancaria',
                                'account_money':'Dinero en Cuenta',
                                'atm':'Cajeros Automáticos',
                                'digital_currency':'Divisa Digital',
                            }
        
        # collection_id
        # collection_status : null, pending (ticket,pse), success (cards,pse), failure (cards, pse)
        # external_reference
        # payment_type : ticket (baloto), cards (visa, mastercard), pse (bancos)
        # merchant_order_id
        # preference_id
        # site_id (MCO) it dependes with account credentials
        # processing_mode : frecuently aggregator
        # merchant_account_id : frecuently null

        site_name = _ml_sites[_response['site_id']][0]
        payment_type_name = _ml_payment_types[_response['payment_type']]
        status = _statusText[_response['collection_status']]

        _response_html = str("<div>")
        _response_html = _response_html + str("<label>")
        _response_html = _response_html + str("Estado: ")
        _response_html = _response_html + str("</label>")
        _response_html = _response_html + str("<span>")
        _response_html = _response_html + str(status)
        _response_html = _response_html + str("</span>")
        _response_html = _response_html + str("</div>")

        

        _response_html = _response_html + str("<div>")
        _response_html = _response_html + str("<label>")
        _response_html = _response_html + str("Localización: ")
        _response_html = _response_html + str("</label>")
        _response_html = _response_html + str("<span>")
        _response_html = _response_html + str(site_name)
        _response_html = _response_html + str("</span>")
        _response_html = _response_html + str("</div>")

        _response_html = _response_html + str("<div>")
        _response_html = _response_html + str("<label>")
        _response_html = _response_html + str("Tipo Pago: ")
        _response_html = _response_html + str("</label>")
        _response_html = _response_html + str("<span>")
        _response_html = _response_html + str(payment_type_name)
        _response_html = _response_html + str("</span>")
        _response_html = _response_html + str("</div>")

        _response_html = _response_html + str("<div>")
        _response_html = _response_html + str("<label>")
        _response_html = _response_html + str("ID Pedido: ")
        _response_html = _response_html + str("</label>")
        _response_html = _response_html + str("<span>")
        _response_html = _response_html + str(_response['merchant_order_id'])
        _response_html = _response_html + str("</span>")
        _response_html = _response_html + str("</div>")

        _response_html = _response_html + str("<div>")
        _response_html = _response_html + str("<label>")
        _response_html = _response_html + str("ID Preferencia: ")
        _response_html = _response_html + str("</label>")
        _response_html = _response_html + str("<span>")
        _response_html = _response_html + str(_response['preference_id'])
        _response_html = _response_html + str("</span>")
        _response_html = _response_html + str("</div>")

        return _response_html