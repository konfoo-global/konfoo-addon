/** @odoo-module **/

import { ComponentWrapper, WidgetAdapterMixin } from 'web.OwlCompatibility';
import Widget from 'web.Widget';
import widgetRegistry from 'web.widget_registry';
import { useService, useBus } from "@web/core/utils/hooks";

const { xml } = owl.tags;
const { useState, onWillUnmount, onWillUpdateProps } = owl.hooks;
const KONFOO_VERBOSE = false;

class KonfooComponent extends owl.Component {
    // 15.0 qweb requires at least one element to be returned for compilation to succeed.
    static template = xml`
        <span>
            <div class="o_konfoo_container" t-if="state.isOpen">
                <iframe class="o_konfoo_iframe" t-att-src="state.config.url" t-on-load="onLoad"></iframe>
            </div>
        </span>
    `;

    async setup() {
        this.rpc = useService('rpc');
        this.notifications = useService('notification');

        this.state = useState({
            isOpen: false,
            config: null,
            iframe: null,
            record_id: null,
            session_key: null,
        });

        useBus(this.env.bus, 'KONFOO_OPEN', data => {
            if (!this.state.config || !this.state.config.url) {
                this.notifications.notify({
                    message: 'Konfoo not configured',
                    type: 'danger',
                    title: 'Konfoo',
                });
                return;
            }

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

                    self.updateState();
                    if (!self.state.record_id) {
                        self.notifications.notify({
                            message: 'Please save the document before clicking Finish in Konfoo.',
                            type: 'warning',
                            title: 'Konfoo',
                        });
                        return;
                    }

                    self.rpc({
                        route: '/konfoo/create',
                        params: {
                            res_id: self.state.record_id,
                            session: e.data.params.session,
                        }
                    })
                    .then(function (_response) {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Create OK');

                        self.close();
                        if (self.props && self.props.legacyWidgetRef) {
                            self.props.legacyWidgetRef.trigger_up('reload');
                        }
                        else {
                            console.warn('Legacy Widget API not available (15.0) - please report this to Konfoo support');
                        }
                    })
                    .then(function() {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Update OK');
                    })
                    .catch(function (err) {
                        if (KONFOO_VERBOSE)
                            console.log('[odoo-konfoo] Error on finish:', JSON.stringify(err));

                        if (typeof(err) === 'object' && err.data) {
                            self.notifications.notify({
                                message: err.data.message,
                                type: 'danger',
                                title: 'Konfoo',
                                sticky: true,
                            });
                        }
                        else if (typeof(err) === 'object' && err.legacy) {
                            self.notifications.notify({
                                message: err.message.data.message,
                                type: 'danger',
                                title: 'Konfoo',
                                sticky: true,
                            });
                        }
                        else {
                            self.notifications.notify({
                                message: err,
                                type: 'danger',
                                title: 'Konfoo',
                                sticky: true,
                            });
                        }
                    });
                    break;
                default:
                    break;
            }
        }

        window.addEventListener('message', onMessage);

        onWillUnmount(() => {
            if (KONFOO_VERBOSE)
                console.log('[odoo-konfoo] unmounting');
            window.removeEventListener('message', onMessage);
        });

        onWillUpdateProps(() => {
            this.updateState();
        });

        this.updateState();

        const clientConfig = await this.rpc({
            route: '/konfoo-client',
        });
        if ('ok' in clientConfig && clientConfig.ok === true) {
            this.state.config = clientConfig;
        }
        else if ('error' in clientConfig) {
            this.notifications.notify({
                message: clientConfig.error,
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
        const iframe = event.target;
        this.state.iframe = event.target;
        if (KONFOO_VERBOSE)
            console.log('[odoo-konfoo] iframe loaded: %s', this.state.iframe ? 'OK' : 'NOT OK');

        if (!this.state.iframe) {
            return;
        }

        iframe.classList.add('o_konfoo_loaded');

        iframe.contentWindow.postMessage({
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
        if (!this.props) {
            return null;
        }
        return this.props.res_id;
    }
}

class KonfooComponentWrapper extends ComponentWrapper {}

const KonfooWidget = Widget.extend(WidgetAdapterMixin, {
    /**
     * @override
     */
    init(parent, props) {
        this._super(...arguments);
        this.props = {
            ...props,
            legacyWidgetRef: this
        };
        this.component = undefined;
    },

    /**
     * @override
     */
    async start() {
        await this._super(...arguments);

        this.component = new KonfooComponentWrapper(
            this,
            KonfooComponent,
            this.props
        );

        await this.component.mount(this.el);
    },
});

widgetRegistry.add('konfoo', KonfooWidget);
export default KonfooWidget;
