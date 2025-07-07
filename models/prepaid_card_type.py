from odoo import models, fields, api
from odoo.exceptions import ValidationError

class NBeautyPrepaidCardType(models.Model):
    _name = 'nbeauty.prepaid.card.type'
    _description = 'Prepaid Card Type'
    _order = 'base_amount asc'

    name = fields.Char(string="Card Name", required=True)
    code = fields.Char(string="Internal Code", help="Short code to identify card type")
    base_amount = fields.Float(string="Top-up Amount (AED)", required=True)
    validity = fields.Selection([
        ('monthly', 'Monthly'),
        ('annual', 'Annual')
    ], string="Validity Period", required=True, default='monthly')

    bonus_percentage = fields.Float(string="Bonus (%)", required=True)
    bonus_amount = fields.Monetary(string="Bonus Value (AED)", compute="_compute_bonus_amount", store=True)

    service_discount = fields.Float(string="Service Discount (%)")
    product_discount = fields.Float(string="Product Discount (%)")

    # allowed_service_ids = fields.Many2many(
    #     'product.template',
    #     'prepaid_card_type_service_rel',
    #     'card_type_id',
    #     'service_id',
    #     string="Allowed Services",
    #     domain=[('type', '=', 'service')],
    # )

    # allowed_product_ids = fields.Many2many(
    #     'product.template',
    #     'prepaid_card_type_product_rel',
    #     'card_type_id',
    #     'product_id',
    #     string="Allowed Products",
    #     domain=[('type', 'in', ['product', 'consu'])],
    # )
    # product_category_ids = fields.Many2many(
    #     'product.category',
    #     'prepaid_card_type_category_rel',
    #     'card_type_id',
    #     'category_id',
    #     string="Allowed Product Categories",
    #     domain=[('name', 'like', 'All//%')],
    #     required=True
    # )

    perks = fields.Text(string="Perks")
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)

    @api.depends('base_amount', 'bonus_percentage')
    def _compute_bonus_amount(self):
        for rec in self:
            rec.bonus_amount = (rec.base_amount * rec.bonus_percentage) / 100 if rec.base_amount and rec.bonus_percentage else 0

    @api.constrains('bonus_percentage')
    def _check_bonus_percentage(self):
        for rec in self:
            if not (0 <= rec.bonus_percentage <= 100):
                raise ValidationError("Bonus percentage must be between 0 and 100.")
