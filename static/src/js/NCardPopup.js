import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class TextInputPopup extends Component {
    static template = "nbeauty_prepaid_card.NCardPopup"; // must match <t t-name="">
    static components = { Dialog };
    static props = {
        title: String,
        buttons: { type: Array, optional: true },
        startingValue: { type: String, optional: true },
        placeholder: { type: String, optional: true },
        rows: { type: Number, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        startingValue: "",
        placeholder: "",
        rows: 1,
        buttons: [],
    };

    setup() {
        this.state = useState({ inputValue: this.props.startingValue });
        this.inputRef = useRef("input");
        onMounted(() => {
            this.inputRef.el.focus();
            this.inputRef.el.select();
        });
    }

    confirm() {
        this.props.getPayload(this.state.inputValue);
        this.props.close();
    }

    close() {
        this.props.close();
    }

    onKeydown(ev) {
        if (this.props.rows === 1 && ev.key === "Enter") {
            this.confirm();
        }
    }
}
