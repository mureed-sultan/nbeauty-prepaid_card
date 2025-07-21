/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

// ------------------------------------------------------
// NCard Popup Component
// ------------------------------------------------------
class NCardPopup extends Component {
    static template = "nbeauty_prepaid_card.NCardPopup";
    static components = { Dialog };
    static props = {
        title: String,
        order: Object,
        paymentMethod: Object,
        close: Function,
        pos: Object,
        autoSearchName: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            cardNo: "",
            cardInfo: undefined,
            error: "",
            searchMode: "card_no",
        });
        this.inputRef = useRef("input");

        onMounted(async () => {
            this.inputRef.el.focus();
            if (this.props.autoSearchName) {
                this.state.searchMode = "name";
                this.state.cardNo = this.props.autoSearchName;
                await this.fetchCardDetails();
            }
        });
    }

    async fetchCardDetails() {
        const query = this.state.cardNo.trim();
        const mode = this.state.searchMode || "card_no";
        this.state.error = "";

        if (!query) {
            this.state.error = "Please enter a value to search.";
            return;
        }

        try {
            const card = await this.env.services.orm.call(
                "nbeauty.prepaid.card",
                "get_card_info",
                [query, mode]
            );

            if (!card) {
                this.state.error = "Card not found.";
                return;
            }

            const orderTotal = this.props.order.get_total_with_tax();
            const isExpired = card.expiry_date && new Date(card.expiry_date) < new Date();

            if (isExpired) {
                this.state.error = "Card is expired.";
                return;
            }

            if (card.state !== "active") {
                this.state.error = "Card is not active.";
                return;
            }

            if (card.balance < orderTotal) {
                this.state.error = "Card has insufficient balance.";
                return;
            }

            this.state.cardInfo = card;
            this.state.error = "";
        } catch (err) {
            this.state.error = "Server error. Try again.";
            console.error("Server error:", err);
        }
    }

    proceed() {
        if (!this.state.cardInfo) {
            this.state.error = "Card not validated.";
            return;
        }

        const cardData = {
            card_no: this.state.cardInfo.card_no,
            previous_balance: this.state.cardInfo.balance,
            amount_used: this.props.order.get_total_with_tax(),
            new_balance: this.state.cardInfo.balance - this.props.order.get_total_with_tax(),
        };

        this.props.order.setNCardData(cardData);
        this.props.order.add_paymentline(this.props.paymentMethod);
        this.props.close({ confirmed: true });
    }

    close() {
        this.props.close({ confirmed: false });
    }
}

// ------------------------------------------------------
// PaymentScreen Patch
// ------------------------------------------------------
patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        if (paymentMethod?.name === "Pay with N Card") {
            const customer = this.currentOrder.get_partner();
            const customerName = customer ? customer.name : "(No customer selected)";
            const { confirmed } = await this.env.services.dialog.add(NCardPopup, {
                title: "Enter NCard Number",
                order: this.currentOrder,
                paymentMethod,
                pos: this.pos,
                autoSearchName: customerName,
            });
            if (!confirmed) return;
            return;
        }
        return await super.addNewPaymentLine(paymentMethod);
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const ncardData = order.getNCardData();

        if (ncardData) {
            try {
                await this.env.services.orm.call(
                    "nbeauty.prepaid.card",
                    "process_ncard_payment",
                    [
                        ncardData.card_no,
                        ncardData.amount_used,
                        order.uuid,
                        order.name || "",
                        null
                    ]
                );

                await this.sendWhatsAppMessage(order, ncardData);

            } catch (err) {
                console.error("❌ Card Payment Error:", err.message || err);
                return;
            }
        }

        await super.validateOrder(isForceValidate);

        if (ncardData) {
            await this.env.services.orm.call(
                "pos.order",
                "api_set_ncard_data",
                [order.uuid, ncardData]
            );
        }
    },

    async sendWhatsAppMessage(order, ncardData) {
        const partner = order.get_partner();
        if (!partner || !partner.mobile) return;

        const phone_number = partner.mobile.replace(/\s+/g, '').replace('+', '');
        const payload = {
            "app-key": "d6342231-fbe0-4bf2-b4b9-9475ccb202be",
            "auth-key": "2d1e0678a72544dbaaf5fc31d2e8b9ec5015c6be085fe44b47",
            "destination_number": phone_number,
            "template_id": "24398846093104422",
            "device_id": "67cfa013e9f65c8638a8fd0b",
            "variables": [
                partner.name || "Customer",
                ncardData.card_no,
                ncardData.amount_used.toFixed(2),
                ncardData.previous_balance.toFixed(2),
                ncardData.new_balance.toFixed(2),
                order.name || "-"
            ],
            "button_variable": [],
            "media": "",
            "message": ""
        };

        try {
            await fetch("https://web.wabridge.com/api/createmessage", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } catch (error) {
            console.warn("❌ WhatsApp Message Failed:", error);
        }
    }
});

// ------------------------------------------------------
// PosOrder Patch
// ------------------------------------------------------
patch(PosOrder.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON();
        if (this.uiState.ncardData) {
            json.ncard_data = this.uiState.ncardData;
        }
        return json;
    },

    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);
        if (this.uiState.ncardData) {
            result.receipt_ncard_data = this.uiState.ncardData;
        }
        return result;
    },

    setNCardData(data) {
        this.uiState.ncardData = data;
    },

    getNCardData() {
        return this.uiState.ncardData || null;
    },
});

// ------------------------------------------------------
// ReceiptScreen Patch (Optional)
// ------------------------------------------------------
patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
    },
});
