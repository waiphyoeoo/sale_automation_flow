from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockMove(models.Model):
    _inherit = 'stock.move'

    def check_allow_negative_stock(self, qtys, product, location, uom):
        onhand = self.get_product_onhand_qty(product, location)
        product_qty = qtys

        try:
            smallest_qty = product_qty / uom.factor * product.uom_id.factor
        except:
            smallest_qty = product_qty

        qtys = abs(smallest_qty)
        if qtys != 0 \
                and qtys > onhand \
                and location.usage in ['internal', 'transit'] \
                and location.allow_negative_stock is False:
            product_name = product.product_tmpl_id.name
            location_name = location.complete_name
            product_uom_name = product.product_tmpl_id.uom_id.name
            raise UserError(
                f'You are trying to move {product_name}({smallest_qty} {product_uom_name}) from {location_name}.But you only have {onhand} {product_uom_name}. If you wanna do negative move, please set allow_negative_stock on {location_name}.')

    def get_product_onhand_qty(self, product, location):
        qty = 0

        if location.id and product.id:
            # included Forecasted Quantity, so we dont use quantity
            quants = self.env['stock.quant']._gather(product, location)
            qty = sum(quants.mapped('quantity'))
        return qty
