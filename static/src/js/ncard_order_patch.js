return

/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

// Add this to your PosOrder export_for_printing patch
patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        console.log("=== DEBUG: export_for_printing called ===");
        console.log("Order UUID:", this.uuid);
        console.log("Order ncard_data:", this.ncard_data);

        const result = super.export_for_printing(baseUrl, headerData);

        if (this.ncard_data) {
            console.log("✅ Adding NCard data to receipt");
            result.receipt_ncard_data = {
                card_no: this.ncard_data.card_no,
                previous_balance: this.ncard_data.previous_balance,
                amount_used: this.ncard_data.amount_used,
                new_balance: this.ncard_data.new_balance,
            };
            console.log("Receipt NCard data:", result.receipt_ncard_data);
        } else {
            console.log("❌ No NCard data found on order");
        }

        console.log("Final receipt object:", result);
        return result;
    },
});