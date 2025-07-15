/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

let runtimeNCardData = null; // ✅ Temporarily store card info


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
        searchMode: "card_no",  // default
    });
    this.inputRef = useRef("input");

    onMounted(async () => {
        this.inputRef.el.focus();

        // 🧠 Auto-search by name if provided
        if (this.props.autoSearchName) {
            this.state.searchMode = "name";
            this.state.cardNo = this.props.autoSearchName;
            await this.fetchCardDetails();  // trigger auto fetch
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
            [query, mode]  // 🟢 Pass both query and mode
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

        const cardId = this.state.cardInfo.id;
        const cardNo = this.state.cardInfo.card_no;
        const balanceBefore = this.state.cardInfo.balance;
        const orderTotal = this.props.order.get_total_with_tax();
        const balanceAfter = balanceBefore - orderTotal;

        // ✅ Store in runtime variable
        runtimeNCardData = {
            card_id: cardId,
            card_no: cardNo,
        };


        this.props.order.add_paymentline(this.props.paymentMethod);

        this.props.close({
            confirmed: true,
            payload: { cardId, cardNo },
        });
    }

    close() {
        this.props.close({ confirmed: false });
    }
}

// 🔧 Patch PaymentScreen
patch(PaymentScreen.prototype, {
    async addNewPaymentLine(paymentMethod) {
        if (paymentMethod?.name === "Pay with N Card") {
             const customer = this.currentOrder.get_partner();
             const customerName = customer ? customer.name : "(No customer selected)";
             console.log("🧾 Selected Customer:", customerName);

            const { confirmed, payload } = await this.env.services.dialog.add(NCardPopup, {
                title: "Enter NCard Number",
                order: this.currentOrder,
                paymentMethod,
                pos: this.pos,
                autoSearchName: customerName, // ✅ pass to popup
            });

            if (!confirmed) {
                return;
            }

            return; // ✅ Payment line was added in popup
        }

        return await super.addNewPaymentLine(paymentMethod);
    },
async validateOrder(isForceValidate) {
    const order = this.currentOrder;
    const totalAmount = order.get_total_with_tax();

      order.get_ncard_data = () => {
            return {
                card_no: order.ncard_no || null,
                previous_balance: order.ncard_previous_balance || 0,
                amount_used: order.ncard_amount_used || 0,
                new_balance: order.ncard_new_balance || 0
            };
        };

    const cardId = runtimeNCardData?.card_id;
    const cardNo = runtimeNCardData?.card_no;

    const orderUID = order?.uuid || "";
    const orderRef = order.name || order.pos_reference || "";
    const branchId = null;

    // Initialize default values
    order.ncard_no = null;
    order.ncard_previous_balance = 0;
    order.ncard_amount_used = 0;
    order.ncard_new_balance = 0;

    if (cardId && totalAmount > 0) {
        try {
            // STEP 1: First get the current card info
            const cardInfo = await this.env.services.orm.call(
                "nbeauty.prepaid.card",
                "get_card_info",
                [cardNo, "card_no"]
            );

            if (!cardInfo) {
                throw new Error("Card information not found");
            }

            // Store card details before processing payment
            order.ncard_no = cardNo;
            order.ncard_previous_balance = cardInfo.balance;
            order.ncard_amount_used = totalAmount;
            order.ncard_new_balance = cardInfo.balance - totalAmount;

            // STEP 2: Process the payment (returns just true/false)
            const paymentSuccess = await this.env.services.orm.call(
                "nbeauty.prepaid.card",
                "process_ncard_payment",
                [cardNo, totalAmount, orderUID, orderRef, branchId]
            );

            if (!paymentSuccess) {
                throw new Error("Payment processing failed");
            }

        } catch (err) {
            // Clear card details if error occurs
            order.ncard_no = null;
            order.ncard_previous_balance = 0;
            order.ncard_amount_used = 0;
            order.ncard_new_balance = 0;

            alert("Card Payment Error: " + (err.message || "Could not deduct from card."));
            console.error("❌ Backend call failed:", err);
            return;
        }
    } else {
        console.warn("⚠️ Skipping card processing (missing card or total amount).");
    }

    runtimeNCardData = null;
    return await super.validateOrder(isForceValidate);
}

});
