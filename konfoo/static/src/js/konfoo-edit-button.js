/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from '@web/core/registry';
import { standardWidgetProps } from '@web/views/widgets/standard_widget_props';

export class KonfooEditButtonComponent extends owl.Component {
    props = owl.useProps(standardWidgetProps);
    static template = owl.xml`<button class="oi btn btn-link" data-icon="edit_square" t-on-click="this.open"></button>`;

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

registry.category('view_widgets').add('konfoo-edit-button', {
    component: KonfooEditButtonComponent,
});
