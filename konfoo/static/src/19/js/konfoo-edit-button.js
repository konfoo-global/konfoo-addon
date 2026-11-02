/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from '@web/core/registry';
import { standardWidgetProps } from '@web/views/widgets/standard_widget_props';

// It is quite inconvenient that `odoo.info` is not available at this point.
import { Widget } from '@web/views/widgets/widget';
const isModernComponentInterface = ('props' in Widget && '*' in Widget.props && Widget.props['*'] === true);

export class KonfooEditButtonComponent extends owl.Component {
    static props = { ...standardWidgetProps, };
    static template = owl.xml`<button class="btn fa fa-pencil-square-o btn-link" t-on-click="open"></button>`;

    open() {
        this.env.bus.trigger('KONFOO_OPEN', {
            record_id: this.getActiveId(),
            konfoo_session_key: this.props.record.data.konfoo_session_key,
        });
    }

    getActiveId() {
        if (!this.props || !this.props.record) {
            return null;
        }

        // Odoo <= 16.0
        if (this.props.record.data && 'id' in this.props.record.data && this.props.record.data.id) {
            return this.props.record.data.id;
        }

        // Odoo >= 17.0
        if (this.props.record.evalContext && this.props.record.evalContext.active_id) {
            return this.props.record.evalContext.active_id;
        }
    }
}

if (isModernComponentInterface) {
    registry.category('view_widgets').add('konfoo-edit-button', {
        component: KonfooEditButtonComponent,
    });
}
else {
    registry.category("view_widgets").add("konfoo-edit-button", KonfooEditButtonComponent);
}
