/** @odoo-module **/
// noinspection DuplicatedCode

import { registry } from '@web/core/registry';
import { useBus, useService } from '@web/core/utils/hooks';
import { standardWidgetProps } from '@web/views/widgets/standard_widget_props';

// It is quite inconvenient that `odoo.info` is not available at this point.
import { Widget } from '@web/views/widgets/widget';
const isModernComponentInterface = ('props' in Widget && '*' in Widget.props && Widget.props['*'] === true);

const KONFOO_VERBOSE = false;

export class KonfooComponent extends owl.Component {
    static props = { ...standardWidgetProps, };
    static template = owl.xml`
        <div t-if="state.isOpen" class="o_konfoo_container">
            <iframe class="o_konfoo_iframe" t-att-src="state.config.url" t-on-load="onLoad"></iframe>
        </div>
    `;

    async setup() {
        this.rpc = useService('rpc');
        this.notifications = useService('notification');

        this.state = owl.useState({
            isOpen: false,
            config: null,
            iframe: null,
            record_id: null,
            session_key: null,
        });

        useBus(this.env.bus, 'KONFOO_OPEN', event => {
            if (!this.state.config || !this.state.config.url) {
                this.notifications.add('Konfoo not configured', {
                    type: 'danger',
                    title: 'Konfoo',
                });
                return;
            }

            const data = event.detail;
            if (data && data.konfoo_session_key) {
                this.state.session_key = data.konfoo_session_key;
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] set session key: %s', this.state.session_key);
            }
            else {
                this.state.session_key = null;
                if (KONFOO_VERBOSE)
                    console.log('[odoo-konfoo] unset session key')
            }
            this.open();
        });

        const self = this;
        function onMessage(e) {
            if (!self.state.config) {
                return;
            }

            if (KONFOO_VERBOSE)
                console.log('[odoo-konfoo] recv:', e.origin, e.data, event.origin);

            if (e.origin !== self.state.config.url) {
                return; // ignore other origins
            }

            if (typeof(e.data) !== 'object' || e.data.type !== 'konfoo') {
                return;
            }

            switch (e.data.cmd) {
                case 'hello':
                    e.source.postMessage({
                        type: 'konfoo',
                        cmd: 'auth',
                        params: { key: self.state.config.client_id },
                    }, e.origin);
                    break;
                case 'start':
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] start:', e.data.params);
                    break;
                case 'discard':
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] discard');
                    self.close();
                    break;
                case 'finish':
                    if (KONFOO_VERBOSE)
                        console.log('[odoo-konfoo] finish:', e.data.params);

                    self.rpc('/konfoo/create', {
                        sale_order_id: self.state.record_id,
                        session: e.data.params.session,
                    })
                    .then(function (_response) {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Create OK');

                        self.close();
                        if (self.props && self.props.record) {
                            return self.props.record.load();
                        }
                    })
                    // .then(function() {
                    //     if (KONFOO_VERBOSE)
                    //         console.log('[odoo-konfoo] Reload OK');
                    //
                    //     if (self.props && self.props.record) {
                    //         return self.props.record.update();
                    //     }
                    // })
                    .then(function() {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Update OK');
                    })
                    .catch(function (err) {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Error on finish:', JSON.stringify(err));

                        if (typeof(err) === 'object' && err.data) {
                            self.notifications.add(err.data.message, {
                                type: 'danger',
                                title: 'Konfoo',
                            });
                        }
                        else {
                            self.notifications.add(err, {
                                type: 'danger',
                                title: 'Konfoo',
                            });
                        }
                    });
                    break;
                default:
                    break;
            }
        }

        window.addEventListener('message', onMessage);

        owl.onWillUnmount(() => {
            if (KONFOO_VERBOSE)
                console.log('[odoo-konfoo] unmounting');
            window.removeEventListener('message', onMessage);
        });

        owl.onWillUpdateProps(() => {
            this.updateState();
        });

        this.updateState();

        const clientConfig = await this.rpc('/konfoo-client');
        if ('ok' in clientConfig && clientConfig.ok === true) {
            this.state.config = clientConfig;
        }
        else if ('error' in clientConfig) {
            this.notifications.add(clientConfig.error, {
                type: 'danger',
                title: 'Konfoo',
            });
        }
    }

    updateState() {
        this.state.record_id = this.getActiveId();
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] update state: record_id = %s', this.state.record_id);
    }

    onLoad(event) {
        this.state.iframe = event.target;
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] iframe loaded: %s', this.state.iframe ? 'OK' : 'NOT OK');

        if (!this.state.iframe) {
            return;
        }

        // TODO: add this to parent so the entire thing transitions
        this.state.iframe.classList.add('o_konfoo_loaded');

        this.state.iframe.contentWindow.postMessage({
            type: 'konfoo',
            cmd: 'hello',
            params: {
                origin: window.origin,
                session: this.state.session_key,
            },
        }, this.state.config.url);
    }

    open() {
        this.state.isOpen = true;
    }

    close() {
        this.state.isOpen = false;
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

export class KonfooButtonComponent extends owl.Component {
    static props = { ...standardWidgetProps, };
    static template = owl.xml
        `<button class="btn btn-primary" t-on-click="open" t-att-disabled="state.disabled">
            <img src="/konfoo/static/src/img/add-product.svg" />
            <span>Konfoo</span>
        </button>`;

    setup() {
        super.setup();

        this.state = owl.useState({
            disabled: true,
        });

        this.updateState();

        owl.onWillUpdateProps(() => {
            this.updateState();
        });
    }

    updateState() {
        this.state.disabled = !this.getActiveId();
    }

    open() {
        this.env.bus.trigger('KONFOO_OPEN');
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
    registry.category('view_widgets').add('konfoo', {
        component: KonfooComponent,
    });

    registry.category('view_widgets').add('konfoo-button', {
        component: KonfooButtonComponent,
    });

    registry.category('view_widgets').add('konfoo-edit-button', {
        component: KonfooEditButtonComponent,
    });
}
else {
    registry.category("view_widgets").add("konfoo", KonfooComponent);
    registry.category("view_widgets").add("konfoo-button", KonfooButtonComponent);
    registry.category("view_widgets").add("konfoo-edit-button", KonfooEditButtonComponent);
}
