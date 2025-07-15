return

/** @odoo-module **/

export const NCardDataStore = {
    ncard_no: null,
    previous_balance: 0,
    amount_used: 0,
    new_balance: 0,

    setData({ ncard_no, previous_balance, amount_used, new_balance }) {
        this.ncard_no = ncard_no;
        this.previous_balance = previous_balance;
        this.amount_used = amount_used;
        this.new_balance = new_balance;
    },

    getData() {
        return {
            ncard_no: this.ncard_no,
            previous_balance: this.previous_balance,
            amount_used: this.amount_used,
            new_balance: this.new_balance,
        };
    },

    reset() {
        this.ncard_no = null;
        this.previous_balance = 0;
        this.amount_used = 0;
        this.new_balance = 0;
    }
};
