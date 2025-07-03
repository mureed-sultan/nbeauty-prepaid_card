from odoo import models, fields, api


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_n_card = fields.Boolean(string='Is N Card Payment')

    @api.model
    def _load_pos_data_fields(self, config_id):
        res = super()._load_pos_data_fields(config_id)
        res += ['is_n_card']
        return res