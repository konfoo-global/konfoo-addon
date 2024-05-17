/** @odoo-module **/

import { ComponentWrapper, WidgetAdapterMixin } from 'web.OwlCompatibility';
import Widget from 'web.Widget';
import widgetRegistry from 'web.widget_registry';

const { xml } = owl.tags;

class KonfooEditButtonComponent extends owl.Component {
    static template = xml`<button class="btn fa fa-pencil-square-o btn-link" t-on-click="open"></button>`;

    open() {
        this.env.bus.trigger('KONFOO_OPEN', {
            record_id: this.getActiveId(),
            konfoo_session_key: this.getKonfooSessionKey(),
        });
    }

    getKonfooSessionKey() {
        if (this.props && this.props.data) {
            return this.props.data.konfoo_session_key;
        }
        return null;
    }

    getActiveId() {
        if (!this.props) {
            return null;
        }
        return this.props.res_id;
    }
}

class KonfooEditButtonComponentWrapper extends ComponentWrapper {}

const KonfooEditButtonWidget = Widget.extend(WidgetAdapterMixin, {
    /**
     * @override
     */
    init(parent, props) {
        this._super(...arguments);
        this.props = props;
        this.component = undefined;
    },

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);

        this.component = new KonfooEditButtonComponentWrapper(
            this,
            KonfooEditButtonComponent,
            this.props
        );
        await this.component.mount(this.el);
    },
});

widgetRegistry.add('konfoo-edit-button', KonfooEditButtonWidget);
export default KonfooEditButtonWidget;
