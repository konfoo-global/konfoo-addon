/** @odoo-module **/

import { ComponentWrapper, WidgetAdapterMixin } from 'web.OwlCompatibility';
import Widget from 'web.Widget';
import widgetRegistry from 'web.widget_registry';

const { xml } = owl.tags;

class KonfooButtonComponent extends owl.Component {
    static template = xml
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

class KonfooButtonComponentWrapper extends ComponentWrapper {}

const KonfooButtonWidget = Widget.extend(WidgetAdapterMixin, {
    /**
     * @override
     */
    init() {
        this._super(...arguments);
        this.component = undefined;
    },

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);

        this.component = new KonfooButtonComponentWrapper(
            this,
            KonfooButtonComponent,
            {}
        );
        await this.component.mount(this.el);
    },
});

widgetRegistry.add('konfoo-button', KonfooButtonWidget);
export default KonfooButtonWidget;
