from odoo import models, fields, api, _
from odoo.exceptions import UserError,ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        # Run default action_confirm
        for line in self.order_line:
            if line.multi_uom_qty > line.product_id.qty_available:
                raise ValidationError(_("Your Product is Not Enough in Stock For Sale"))
            else:
                res = super(SaleOrder, self).action_confirm()
                if self.sale_type == 'normal':
                    # Update onhand qty
                    for line in self.order_line:
                        line.available_qty_by_warehouse = line.get_product_onhand_qty()

                    # Confirm pickings
                    pickings_to_validate = self.picking_ids.filtered(lambda p: p.state not in ['cancel', 'done'])
                    if pickings_to_validate:
                        for picking in pickings_to_validate:
                            for move in picking.move_ids_without_package:
                                move.check_allow_negative_stock(move.product_uom_qty, move.product_id, move.location_id,
                                                                move.product_uom)
                                move.quantity_done = move.product_uom_qty

                            picking.action_assign()
                            picking.move_lines._set_quantities_to_reservation()
                            picking.action_confirm()

                        # Skip backorder validate picking with only available qty
                        pickings_to_validate.with_context(picking_ids_not_to_backorder=[picking.id], skip_immediate=True,
                                                          skip_backorder=True).button_validate()

                    # Create Invoice
                    self._create_invoices()
                    invoices_to_confirm = self.invoice_ids.filtered(lambda p: p.state not in ['cancel', 'posted'])

                    if invoices_to_confirm:
                        # Trigger the Scheduler for Invoices
                        invoices_to_confirm.action_post()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    available_qty_by_warehouse = fields.Float(string='Qty on Hand', readonly=True, digits="Product Unit of Measure")

    def get_product_onhand_qty(self):
        qty = 0
        location_id = self.warehouse_id.lot_stock_id
        if location_id and self.product_id and self.warehouse_id:
            # Include child internal locations of lot_stock and child internal locations of lot_stock's parent location
            all_internal_locations = self.warehouse_id.lot_stock_id.child_internal_location_ids.mapped('id')
            if self.warehouse_id.lot_stock_id.location_id:
                all_internal_locations.extend(
                    [*self.warehouse_id.lot_stock_id.location_id.child_internal_location_ids.mapped('id')])

            unique_all_internal_locations = list(set(all_internal_locations))

            # Not included Forecasted Quantity, so we dont use availableQty
            quants = self.env['stock.quant'].search(
                [('product_id', '=', self.product_id.id), ('location_id', 'in', unique_all_internal_locations)]).mapped(
                'quantity')
            qty = sum(quants)

        return qty
