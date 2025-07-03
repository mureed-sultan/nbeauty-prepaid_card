# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class ./custom_addons/nbeauty_prepaid_card(models.Model):
#     _name = './custom_addons/nbeauty_prepaid_card../custom_addons/nbeauty_prepaid_card'
#     _description = './custom_addons/nbeauty_prepaid_card../custom_addons/nbeauty_prepaid_card'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

