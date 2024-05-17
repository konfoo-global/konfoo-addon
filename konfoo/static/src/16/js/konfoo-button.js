/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from '@web/core/registry';
import { standardWidgetProps } from '@web/views/widgets/standard_widget_props';

export class KonfooButtonComponent extends owl.Component {
    static props = { ...standardWidgetProps, };
    static template = owl.xml
        `<button class="btn btn-primary" t-on-click="open">
            <img src="/konfoo/static/src/img/add-product.svg" />
            <span>Konfoo</span>
        </button>`;

    setup() {
        super.setup();
    }

    open() {
        this.env.bus.trigger('KONFOO_OPEN');
    }
}

registry.category("view_widgets").add("konfoo-button", KonfooButtonComponent);
