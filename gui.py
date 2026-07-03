import asyncio
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timezone

SIDE_LABELS = {"1": "Buy", "2": "Sell", "5": "Sell Short", "6": "Sell Short Ex"}
TYPE_LABELS = {"1": "Market", "2": "Limit"}


def _now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:12]


class FixOrderGui:
    def __init__(self, root, fix_client, fix_server, loop):
        self.root = root
        self.client = fix_client
        self.server = fix_server
        self.loop = loop
        self.root.title("FIX Order Entry")
        self.root.geometry("1200x750")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_widgets()
        self._log_client("FIX Order Entry started")
        self._log_server("FIX Order Entry started")

    def _log_client(self, text):
        self.cli_log_area.config(state=tk.NORMAL)
        self.cli_log_area.insert(tk.END, f"[{_now()}] {text}\n")
        self.cli_log_area.see(tk.END)
        self.cli_log_area.config(state=tk.DISABLED)

    def _log_server(self, text):
        self.srv_log_area.config(state=tk.NORMAL)
        self.srv_log_area.insert(tk.END, f"[{_now()}] {text}\n")
        self.srv_log_area.see(tk.END)
        self.srv_log_area.config(state=tk.DISABLED)

    def set_client_status(self, text):
        self.cli_status_lbl.config(text=f"Client: {text}")

    def set_server_status(self, text):
        self.srv_status_lbl.config(text=f"Server: {text}")

    def _build_widgets(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)

        self._build_order_entry_tab(nb)
        self._build_orders_tab(nb)
        self._build_client_orders_tab(nb)
        self._build_connection_tab(nb)

        log_frame = ttk.Frame(main)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.columnconfigure(1, weight=1)
        log_frame.rowconfigure(1, weight=1)

        ttk.Label(log_frame, text="Client Log:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5)
        )
        ttk.Label(log_frame, text="Server Log:").grid(
            row=0, column=1, sticky=tk.W, padx=(5, 0)
        )

        self.cli_log_area = scrolledtext.ScrolledText(
            log_frame, height=8, state=tk.DISABLED,
            font=("Consolas", 9),
        )
        self.cli_log_area.grid(row=1, column=0, sticky=tk.NSEW, padx=(0, 2))

        self.srv_log_area = scrolledtext.ScrolledText(
            log_frame, height=8, state=tk.DISABLED,
            font=("Consolas", 9),
        )
        self.srv_log_area.grid(row=1, column=1, sticky=tk.NSEW, padx=(2, 0))

    def _build_order_entry_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Order Entry ")
        r = 0

        ttk.Label(f, text="Symbol:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.symbol_var = tk.StringVar(value="AAPL")
        ttk.Entry(f, textvariable=self.symbol_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(f, text="Side:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.side_var = tk.StringVar(value="1")
        ttk.Combobox(
            f, textvariable=self.side_var,
            values=[f"{k} - {v}" for k, v in SIDE_LABELS.items()],
            state="readonly", width=25,
        ).grid(row=r, column=1, sticky=tk.W, pady=2)
        r += 1

        ttk.Label(f, text="Order Type:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.ord_type_var = tk.StringVar(value="1")
        ttk.Combobox(
            f, textvariable=self.ord_type_var,
            values=[f"{k} - {v}" for k, v in TYPE_LABELS.items()],
            state="readonly", width=25,
        ).grid(row=r, column=1, sticky=tk.W, pady=2)
        r += 1

        ttk.Label(f, text="Quantity:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.qty_var = tk.StringVar(value="100")
        ttk.Entry(f, textvariable=self.qty_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(f, text="Price:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.price_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.price_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        ttk.Label(f, text="(blank for Market)").grid(
            row=r, column=2, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(f, text="HandlInst:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.handl_inst_var = tk.StringVar(value="1")
        ttk.Combobox(
            f, textvariable=self.handl_inst_var,
            values=["1 - Automated", "2 - Broker", "3 - Manual"],
            state="readonly", width=25,
        ).grid(row=r, column=1, sticky=tk.W, pady=2)
        r += 1

        ttk.Label(f, text="TimeInForce:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.time_in_force_var = tk.StringVar(value="0")
        ttk.Combobox(
            f, textvariable=self.time_in_force_var,
            values=["0 - Day", "1 - GTC", "3 - IOC", "4 - FOK", "6 - GTD"],
            state="readonly", width=25,
        ).grid(row=r, column=1, sticky=tk.W, pady=2)
        r += 1

        ttk.Label(f, text="Account:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.account_var = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.account_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Separator(f, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky=tk.EW, pady=10
        )
        r += 1

        ttk.Button(f, text="Send Order", command=self._on_send_order).grid(
            row=r, column=1, pady=5
        )

    def _build_orders_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Server Orders ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        cols = ("clord_id", "order_id", "exec_id", "symbol", "side", "qty", "type",
                "price", "last_px", "leaves_qty", "handl_inst", "time_in_force",
                "transact_time", "status", "sending_time")
        self.order_tree = ttk.Treeview(f, columns=cols, show="headings",
                                       selectmode="browse")
        headings = {
            "clord_id": "ClOrdID",
            "order_id": "OrderID",
            "exec_id": "ExecID",
            "symbol": "Symbol",
            "side": "Side",
            "qty": "Qty",
            "type": "Type",
            "price": "Price",
            "last_px": "LastPx",
            "leaves_qty": "LeavesQty",
            "handl_inst": "HandlInst",
            "time_in_force": "TIF",
            "transact_time": "TransactTime",
            "status": "Status",
            "sending_time": "SendingTime",
        }
        widths = {"clord_id": 150, "order_id": 150, "exec_id": 150, "symbol": 65,
                  "side": 55, "qty": 55, "type": 65, "price": 65, "last_px": 65,
                  "leaves_qty": 65, "handl_inst": 70, "time_in_force": 50,
                  "transact_time": 150, "status": 100, "sending_time": 150}
        for c in cols:
            self.order_tree.heading(c, text=headings[c])
            self.order_tree.column(c, width=widths[c], anchor=tk.CENTER)

        scroll = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self.order_tree.yview)
        self.order_tree.configure(yscrollcommand=scroll.set)
        self.order_tree.grid(row=0, column=0, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, sticky=tk.NS)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=8)

        self.acc_btn = ttk.Button(
            btn_frame, text="Accept", command=self._on_accept_order,
            state=tk.DISABLED,
        )
        self.acc_btn.pack(side=tk.LEFT, padx=5)

        self.rej_btn = ttk.Button(
            btn_frame, text="Reject", command=self._on_reject_order,
            state=tk.DISABLED,
        )
        self.rej_btn.pack(side=tk.LEFT, padx=5)

        self.exec_btn = ttk.Button(
            btn_frame, text="Executed", command=self._on_executed_order,
            state=tk.DISABLED,
        )
        self.exec_btn.pack(side=tk.LEFT, padx=5)

        self.order_tree.bind("<<TreeviewSelect>>", self._on_order_select)

    def _build_client_orders_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Client Orders ")
        f.columnconfigure(0, weight=1)
        f.rowconfigure(0, weight=1)

        cols = ("clord_id", "order_id", "exec_id", "symbol", "side", "qty", "type",
                "price", "last_px", "leaves_qty", "handl_inst", "time_in_force",
                "transact_time", "status", "sending_time")
        self.client_order_tree = ttk.Treeview(f, columns=cols, show="headings",
                                              selectmode="browse")
        headings = {
            "clord_id": "ClOrdID",
            "order_id": "OrderID",
            "exec_id": "ExecID",
            "symbol": "Symbol",
            "side": "Side",
            "qty": "Qty",
            "type": "Type",
            "price": "Price",
            "last_px": "LastPx",
            "leaves_qty": "LeavesQty",
            "handl_inst": "HandlInst",
            "time_in_force": "TIF",
            "transact_time": "TransactTime",
            "status": "Status",
            "sending_time": "SendingTime",
        }
        widths = {"clord_id": 150, "order_id": 150, "exec_id": 150, "symbol": 65,
                  "side": 55, "qty": 55, "type": 65, "price": 65, "last_px": 65,
                  "leaves_qty": 65, "handl_inst": 70, "time_in_force": 50,
                  "transact_time": 150, "status": 100, "sending_time": 150}
        for c in cols:
            self.client_order_tree.heading(c, text=headings[c])
            self.client_order_tree.column(c, width=widths[c], anchor=tk.CENTER)

        scroll = ttk.Scrollbar(f, orient=tk.VERTICAL,
                               command=self.client_order_tree.yview)
        self.client_order_tree.configure(yscrollcommand=scroll.set)
        self.client_order_tree.grid(row=0, column=0, sticky=tk.NSEW)
        scroll.grid(row=0, column=1, sticky=tk.NS)

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=8)

        self.cancel_btn = ttk.Button(
            btn_frame, text="Cancel", command=self._on_cancel_order,
            state=tk.DISABLED,
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        self.modify_btn = ttk.Button(
            btn_frame, text="Modify", command=self._on_modify_order,
            state=tk.DISABLED,
        )
        self.modify_btn.pack(side=tk.LEFT, padx=5)

        self.client_order_tree.bind("<<TreeviewSelect>>",
                                    self._on_client_order_select)

    def _build_connection_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Connection ")

        # ── Client section ──────────────────────────────────
        bigr = 0
        lf = ttk.LabelFrame(f, text="FIX Client", padding=10)
        lf.grid(row=bigr, column=0, sticky=tk.EW, padx=5, pady=5)
        bigr += 1

        r = 0
        ttk.Label(lf, text="Role:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.cli_role_var = tk.StringVar(
            value=self.client.cfg.get("client_role", "INITIATOR")
        )
        self.cli_role_menu = ttk.Combobox(
            lf, textvariable=self.cli_role_var,
            values=["INITIATOR", "ACCEPTOR"],
            state="readonly", width=22,
        )
        self.cli_role_menu.grid(row=r, column=1, sticky=tk.W, pady=2)
        self.cli_role_menu.bind("<<ComboboxSelected>>", self._on_cli_role_change)
        r += 1

        ttk.Label(lf, text="Host:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.host_var = tk.StringVar(value=self.client.cfg.get("host", "127.0.0.1"))
        ttk.Entry(lf, textvariable=self.host_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="Port:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value=str(self.client.cfg.get("port", 9823)))
        ttk.Entry(lf, textvariable=self.port_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="SenderCompID:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.sender_var = tk.StringVar(
            value=self.client.cfg.get("sender_comp_id", "SENDER")
        )
        ttk.Entry(lf, textvariable=self.sender_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="TargetCompID:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.target_var = tk.StringVar(
            value=self.client.cfg.get("target_comp_id", "TARGET")
        )
        ttk.Entry(lf, textvariable=self.target_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="Username:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.user_var = tk.StringVar(value=self.client.cfg.get("username", "user"))
        ttk.Entry(lf, textvariable=self.user_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="Password:").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.pass_var = tk.StringVar(value=self.client.cfg.get("password", "password"))
        ttk.Entry(lf, textvariable=self.pass_var, width=25, show="*").grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        ttk.Label(lf, text="Heartbeat (sec):").grid(row=r, column=0, sticky=tk.W, pady=2)
        self.cli_hb_var = tk.StringVar(
            value=str(self.client.cfg.get("heartbeat_interval", 30))
        )
        ttk.Entry(lf, textvariable=self.cli_hb_var, width=25).grid(
            row=r, column=1, sticky=tk.W, pady=2
        )
        r += 1

        self.cli_reset_seq_var = tk.BooleanVar(
            value=self.client.cfg.get("client_reset_seq", True)
        )
        ttk.Checkbutton(
            lf, text="Reset Seq Nums on Logon",
            variable=self.cli_reset_seq_var,
        ).grid(row=r, column=0, columnspan=2, sticky=tk.W, pady=2)
        r += 1

        btn_f = ttk.Frame(lf)
        btn_f.grid(row=r, column=0, columnspan=2, pady=6)
        self.connect_btn = ttk.Button(
            btn_f, text="Connect", command=self._on_connect
        )
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        self.disconnect_btn = ttk.Button(
            btn_f, text="Disconnect", command=self._on_disconnect,
            state=tk.DISABLED,
        )
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

        self.cli_status_lbl = ttk.Label(lf, text="Client: Disconnected",
                                        foreground="red")
        self.cli_status_lbl.grid(row=r + 1, column=0, columnspan=2,
                                 pady=4, sticky=tk.W)

        # ── Server section ──────────────────────────────────
        sf = ttk.LabelFrame(f, text="FIX Server", padding=10)
        sf.grid(row=bigr, column=0, sticky=tk.EW, padx=5, pady=5)
        bigr += 1

        sr = 0
        ttk.Label(sf, text="Role:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_role_var = tk.StringVar(
            value=self.server.cfg.get("server_role", "ACCEPTOR")
        )
        self.srv_role_menu = ttk.Combobox(
            sf, textvariable=self.srv_role_var,
            values=["ACCEPTOR", "INITIATOR"],
            state="readonly", width=22,
        )
        self.srv_role_menu.grid(row=sr, column=1, sticky=tk.W, pady=2)
        self.srv_role_menu.bind("<<ComboboxSelected>>", self._on_srv_role_change)
        sr += 1

        ttk.Label(sf, text="Host:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_host_var = tk.StringVar(
            value=self.server.cfg.get("server_host", "127.0.0.1")
        )
        self.srv_host_entry = ttk.Entry(sf, textvariable=self.srv_host_var, width=25)
        self.srv_host_entry.grid(row=sr, column=1, sticky=tk.W, pady=2)
        sr += 1

        ttk.Label(sf, text="Port:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_port_var = tk.StringVar(
            value=str(self.server.cfg.get("server_port", 9823))
        )
        self.srv_port_entry = ttk.Entry(sf, textvariable=self.srv_port_var, width=25)
        self.srv_port_entry.grid(row=sr, column=1, sticky=tk.W, pady=2)
        sr += 1

        ttk.Label(sf, text="SenderCompID:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_sender_var = tk.StringVar(
            value=self.server.cfg.get("server_sender_comp_id", "SERVER")
        )
        ttk.Entry(sf, textvariable=self.srv_sender_var, width=25).grid(
            row=sr, column=1, sticky=tk.W, pady=2
        )
        sr += 1

        ttk.Label(sf, text="TargetCompID:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_target_var = tk.StringVar(
            value=self.server.cfg.get("server_target_comp_id", "CLIENT")
        )
        ttk.Entry(sf, textvariable=self.srv_target_var, width=25).grid(
            row=sr, column=1, sticky=tk.W, pady=2
        )
        sr += 1

        ttk.Label(sf, text="Target Host:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_tgt_host_var = tk.StringVar(
            value=self.server.cfg.get("server_target_host", "127.0.0.1")
        )
        self.srv_tgt_host_entry = ttk.Entry(
            sf, textvariable=self.srv_tgt_host_var, width=25
        )
        self.srv_tgt_host_entry.grid(row=sr, column=1, sticky=tk.W, pady=2)
        sr += 1

        ttk.Label(sf, text="Target Port:").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_tgt_port_var = tk.StringVar(
            value=str(self.server.cfg.get("server_target_port", 9824))
        )
        self.srv_tgt_port_entry = ttk.Entry(
            sf, textvariable=self.srv_tgt_port_var, width=25
        )
        self.srv_tgt_port_entry.grid(row=sr, column=1, sticky=tk.W, pady=2)
        sr += 1

        ttk.Label(sf, text="Heartbeat (sec):").grid(row=sr, column=0, sticky=tk.W, pady=2)
        self.srv_hb_var = tk.StringVar(
            value=str(self.server.cfg.get("heartbeat_interval", 30))
        )
        ttk.Entry(sf, textvariable=self.srv_hb_var, width=25).grid(
            row=sr, column=1, sticky=tk.W, pady=2
        )
        sr += 1

        self.srv_reset_seq_var = tk.BooleanVar(
            value=self.server.cfg.get("server_reset_seq", True)
        )
        ttk.Checkbutton(
            sf, text="Reset Seq Nums on Logon",
            variable=self.srv_reset_seq_var,
        ).grid(row=sr, column=0, columnspan=2, sticky=tk.W, pady=2)
        sr += 1

        srv_btn_f = ttk.Frame(sf)
        srv_btn_f.grid(row=sr, column=0, columnspan=2, pady=6)
        self.start_srv_btn = ttk.Button(
            srv_btn_f, text="Start Server", command=self._on_start_server
        )
        self.start_srv_btn.pack(side=tk.LEFT, padx=5)
        self.stop_srv_btn = ttk.Button(
            srv_btn_f, text="Stop Server", command=self._on_stop_server,
            state=tk.DISABLED,
        )
        self.stop_srv_btn.pack(side=tk.LEFT, padx=5)

        self.srv_status_lbl = ttk.Label(sf, text="Server: Stopped",
                                        foreground="red")
        self.srv_status_lbl.grid(row=sr + 1, column=0, columnspan=2,
                                 pady=4, sticky=tk.W)

        self._on_srv_role_change()

    # ── Order callbacks (called from server thread) ────────
    def _fmt_sending_time(self, raw):
        if not raw:
            return ""
        s = raw.replace("T", "-")
        if len(s) >= 19:
            return s[:19]
        return s

    def add_order(self, order):
        self.order_tree.insert(
            "", tk.END,
            iid=order["clord_id"],
            values=(
                order["clord_id"],
                order.get("order_id", ""),
                order.get("exec_id", ""),
                order["symbol"],
                SIDE_LABELS.get(order["side"], order["side"]),
                order["qty"],
                TYPE_LABELS.get(order["ord_type"], order["ord_type"]),
                f'{order["price"]:.2f}' if order["price"] else "MKT",
                f'{order["last_px"]:.2f}' if order.get("last_px") else "",
                order.get("leaves_qty", ""),
                order.get("handl_inst", ""),
                order.get("time_in_force", ""),
                self._fmt_sending_time(order.get("transact_time", "")),
                order["status"],
                self._fmt_sending_time(order.get("sending_time", "")),
            ),
        )

    def update_order(self, order):
        iid = order["clord_id"]
        if self.order_tree.exists(iid):
            self.order_tree.item(
                iid,
                values=(
                    order["clord_id"],
                    order.get("order_id", ""),
                    order.get("exec_id", ""),
                    order["symbol"],
                    SIDE_LABELS.get(order["side"], order["side"]),
                    order["qty"],
                    TYPE_LABELS.get(order["ord_type"], order["ord_type"]),
                    f'{order["price"]:.2f}' if order["price"] else "MKT",
                    f'{order["last_px"]:.2f}' if order.get("last_px") else "",
                    order.get("leaves_qty", ""),
                    order.get("handl_inst", ""),
                    order.get("time_in_force", ""),
                    self._fmt_sending_time(order.get("transact_time", "")),
                    order["status"],
                    self._fmt_sending_time(order.get("sending_time", "")),
                ),
            )

    # ── Client order callbacks (called from client thread) ─
    def add_client_order(self, clord_id, order):
        if self.client_order_tree.exists(clord_id):
            self.update_client_order(clord_id, order)
            return
        self.client_order_tree.insert(
            "", tk.END,
            iid=clord_id,
            values=(
                clord_id,
                order.get("order_id", ""),
                order.get("exec_id", ""),
                order["symbol"],
                SIDE_LABELS.get(order["side"], order["side"]),
                order["qty"],
                TYPE_LABELS.get(order["type"], order["type"]),
                f'{order["price"]:.2f}' if order["price"] else "MKT",
                f'{order["last_px"]:.2f}' if order.get("last_px") else "",
                order.get("leaves_qty", ""),
                order.get("handl_inst", ""),
                order.get("time_in_force", ""),
                self._fmt_sending_time(order.get("transact_time", "")),
                order.get("status", "Sent"),
                self._fmt_sending_time(order.get("sending_time", "")),
            ),
        )

    def update_client_order(self, clord_id, order):
        if self.client_order_tree.exists(clord_id):
            self.client_order_tree.item(
                clord_id,
                values=(
                    clord_id,
                    order.get("order_id", ""),
                    order.get("exec_id", ""),
                    order["symbol"],
                    SIDE_LABELS.get(order["side"], order["side"]),
                    order["qty"],
                    TYPE_LABELS.get(order["type"], order["type"]),
                    f'{order["price"]:.2f}' if order["price"] else "MKT",
                    f'{order["last_px"]:.2f}' if order.get("last_px") else "",
                    order.get("leaves_qty", ""),
                    order.get("handl_inst", ""),
                    order.get("time_in_force", ""),
                    self._fmt_sending_time(order.get("transact_time", "")),
                    order.get("status", "Sent"),
                    self._fmt_sending_time(order.get("sending_time", "")),
                ),
            )

    # ── Role toggles ───────────────────────────────────────
    def _on_cli_role_change(self, event=None):
        pass

    def _on_srv_role_change(self, event=None):
        is_acc = self.srv_role_var.get() == "ACCEPTOR"
        state = tk.NORMAL if is_acc else tk.DISABLED
        self.srv_host_entry.config(state=state)
        self.srv_port_entry.config(state=state)
        state = tk.NORMAL if not is_acc else tk.DISABLED
        self.srv_tgt_host_entry.config(state=state)
        self.srv_tgt_port_entry.config(state=state)

    # ── Handlers ───────────────────────────────────────────
    def _on_order_select(self, event):
        sel = self.order_tree.selection()
        if sel:
            vals = self.order_tree.item(sel[0], "values")
            if vals:
                st = vals[-2]
                if st == "Pending":
                    self.acc_btn.config(state=tk.NORMAL, text="Accept")
                    self.rej_btn.config(state=tk.NORMAL, text="Reject")
                    self.exec_btn.config(state=tk.NORMAL)
                    return
                if st in ("Acknowledged", "PartiallyFilled"):
                    self.acc_btn.config(state=tk.DISABLED)
                    self.rej_btn.config(state=tk.DISABLED)
                    self.exec_btn.config(state=tk.NORMAL)
                    return
                if st == "CancelPending":
                    self.acc_btn.config(state=tk.NORMAL, text="Approve Cancel")
                    self.rej_btn.config(state=tk.NORMAL, text="Reject Cancel")
                    self.exec_btn.config(state=tk.DISABLED)
                    return
                if st == "ModifyPending":
                    self.acc_btn.config(state=tk.NORMAL, text="Approve Modify")
                    self.rej_btn.config(state=tk.NORMAL, text="Reject Modify")
                    self.exec_btn.config(state=tk.DISABLED)
                    return
        self.acc_btn.config(state=tk.DISABLED)
        self.rej_btn.config(state=tk.DISABLED)
        self.exec_btn.config(state=tk.DISABLED)

    def _on_accept_order(self):
        sel = self.order_tree.selection()
        if not sel:
            return
        clord_id = sel[0]
        st = ""
        if self.order_tree.exists(clord_id):
            vals = self.order_tree.item(clord_id, "values")
            st = vals[-2] if vals else ""
        if st == "CancelPending":
            asyncio.run_coroutine_threadsafe(
                self.server.approve_cancel(clord_id), self.loop
            )
            self._log_server(f"Cancel approved for order {clord_id}")
        elif st == "ModifyPending":
            asyncio.run_coroutine_threadsafe(
                self.server.approve_modify(clord_id), self.loop
            )
            self._log_server(f"Modify approved for order {clord_id}")
        else:
            asyncio.run_coroutine_threadsafe(
                self.server.acknowledge_order(clord_id), self.loop
            )
            self._log_server(f"Accepted order {clord_id}")

    def _on_reject_order(self):
        sel = self.order_tree.selection()
        if not sel:
            return
        clord_id = sel[0]
        st = ""
        if self.order_tree.exists(clord_id):
            vals = self.order_tree.item(clord_id, "values")
            st = vals[-2] if vals else ""
        if st == "CancelPending":
            asyncio.run_coroutine_threadsafe(
                self.server.reject_cancel(clord_id), self.loop
            )
            self._log_server(f"Cancel rejected for order {clord_id}")
        elif st == "ModifyPending":
            asyncio.run_coroutine_threadsafe(
                self.server.reject_modify(clord_id), self.loop
            )
            self._log_server(f"Modify rejected for order {clord_id}")
        else:
            asyncio.run_coroutine_threadsafe(
                self.server.reject_order(clord_id), self.loop
            )
            self._log_server(f"Rejected order {clord_id}")

    def _on_executed_order(self):
        sel = self.order_tree.selection()
        if not sel:
            return
        clord_id = sel[0]
        vals = self.order_tree.item(clord_id, "values")
        order_qty = vals[5]

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Execute Order {clord_id}")
        dlg.transient(self.root)
        dlg.grab_set()

        f = ttk.Frame(dlg, padding=15)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text=f"Order Qty: {order_qty}").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        ttk.Label(f, text="Executed Qty:").grid(
            row=1, column=0, sticky=tk.W, pady=3
        )
        qty_var = tk.StringVar(value=order_qty)
        ttk.Entry(f, textvariable=qty_var, width=25).grid(
            row=1, column=1, sticky=tk.W, pady=3
        )

        ttk.Label(f, text="Executed Price:").grid(
            row=2, column=0, sticky=tk.W, pady=3
        )
        price_var = tk.StringVar(value=vals[7] if vals[7] != "MKT" else "")
        ttk.Entry(f, textvariable=price_var, width=25).grid(
            row=2, column=1, sticky=tk.W, pady=3
        )

        def do_execute():
            try:
                ex_qty = float(qty_var.get().strip())
                if ex_qty <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Invalid", "Executed qty must be > 0")
                return
            ex_price_str = price_var.get().strip()
            try:
                ex_price = float(ex_price_str) if ex_price_str else 0.0
            except ValueError:
                messagebox.showwarning("Invalid", "Executed price must be a number")
                return
            asyncio.run_coroutine_threadsafe(
                self.server.execute_order(clord_id, ex_qty, ex_price), self.loop
            )
            self._log_server(f"Executed order {clord_id}: qty={ex_qty} @ {ex_price}")
            dlg.destroy()

        btn_f = ttk.Frame(f)
        btn_f.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_f, text="Submit", command=do_execute).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_f, text="Cancel", command=dlg.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def _on_client_order_select(self, event):
        sel = self.client_order_tree.selection()
        if sel:
            vals = self.client_order_tree.item(sel[0], "values")
            if vals:
                st = vals[-2]
                can_act = st in ("Sent", "New", "PartiallyFilled", "Pending")
                self.cancel_btn.config(state=tk.NORMAL if can_act else tk.DISABLED)
                self.modify_btn.config(state=tk.NORMAL if can_act else tk.DISABLED)
                return
        self.cancel_btn.config(state=tk.DISABLED)
        self.modify_btn.config(state=tk.DISABLED)

    def _on_cancel_order(self):
        sel = self.client_order_tree.selection()
        if not sel:
            return
        clord_id = sel[0]
        asyncio.run_coroutine_threadsafe(
            self.client.cancel_order(clord_id), self.loop
        )
        self._log_client(f"Cancel request sent for order {clord_id}")

    def _on_modify_order(self):
        sel = self.client_order_tree.selection()
        if not sel:
            return
        clord_id = sel[0]
        vals = self.client_order_tree.item(clord_id, "values")

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Modify Order {clord_id}")
        dlg.transient(self.root)
        dlg.grab_set()

        f = ttk.Frame(dlg, padding=15)
        f.pack(fill=tk.BOTH, expand=True)

        fields = {}
        r = 0
        for label, key, default in [
            ("Symbol", "symbol", vals[3]),
            ("Side", "side", vals[4]),
            ("Quantity", "qty", vals[5]),
            ("Type", "type", vals[6]),
            ("Price", "price", vals[7]),
        ]:
            ttk.Label(f, text=label + ":").grid(row=r, column=0, sticky=tk.W, pady=3)
            var = tk.StringVar(value=default)
            if key == "side":
                w = ttk.Combobox(f, textvariable=var,
                                 values=list(SIDE_LABELS.values()),
                                 state="readonly", width=22)
            elif key == "type":
                w = ttk.Combobox(f, textvariable=var,
                                 values=list(TYPE_LABELS.values()),
                                 state="readonly", width=22)
            else:
                w = ttk.Entry(f, textvariable=var, width=25)
            w.grid(row=r, column=1, sticky=tk.W, pady=3)
            fields[key] = var
            r += 1

        def do_modify():
            symbol = fields["symbol"].get().strip()
            side_raw = fields["side"].get().split(" - ")[0]
            side_rev = {v: k for k, v in SIDE_LABELS.items()}
            side = side_rev.get(side_raw, "1")
            try:
                qty = float(fields["qty"].get().strip())
            except ValueError:
                messagebox.showwarning("Invalid", "Quantity must be a number")
                return
            type_raw = fields["type"].get().split(" - ")[0]
            type_rev = {v: k for k, v in TYPE_LABELS.items()}
            ord_type = type_rev.get(type_raw, "1")
            price_str = fields["price"].get().strip()
            price = float(price_str) if price_str and price_str != "MKT" else 0.0
            asyncio.run_coroutine_threadsafe(
                self.client.modify_order(clord_id, symbol, side, qty, ord_type, price),
                self.loop,
            )
            self._log_client(f"Modify request sent for order {clord_id}")
            dlg.destroy()

        btn_f = ttk.Frame(f)
        btn_f.grid(row=r, column=0, columnspan=2, pady=10)
        ttk.Button(btn_f, text="Submit", command=do_modify).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_f, text="Cancel", command=dlg.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def _on_send_order(self):
        symbol = self.symbol_var.get().strip()
        if not symbol:
            messagebox.showwarning("Validation", "Symbol is required")
            return
        side_raw = self.side_var.get().split(" - ")[0]
        ord_raw = self.ord_type_var.get().split(" - ")[0]
        try:
            qty = float(self.qty_var.get().strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Validation", "Quantity must be > 0")
            return
        price_str = self.price_var.get().strip()
        price = float(price_str) if price_str else 0.0
        account = self.account_var.get().strip() or None
        handl_inst = self.handl_inst_var.get().split(" - ")[0]
        time_in_force = self.time_in_force_var.get().split(" - ")[0]

        fut = asyncio.run_coroutine_threadsafe(
            self._do_send_order(symbol, side_raw, qty, ord_raw, price, account,
                                handl_inst, time_in_force),
            self.loop,
        )
        fut.add_done_callback(self._on_send_order_done)

    def _on_send_order_done(self, fut):
        try:
            fut.result()
        except Exception as e:
            self.root.after(0, self._log_client, f"ERROR sending order: {e}")

    async def _do_send_order(self, symbol, side, qty, ord_type, price, account,
                             handl_inst="1", time_in_force="0"):
        if not self.client._logged_on:
            self._log_client("ERROR: Not logged on")
            return
        try:
            clord_id = await self.client.send_order(
                symbol, side, qty, ord_type, price, account, handl_inst, time_in_force
            )
        except Exception as e:
            self._log_client(f"ERROR: send_order failed: {e}")
            return
        self._log_client(
            f"Sent order ClOrdID={clord_id} {symbol} "
            f"{SIDE_LABELS.get(side, side)} qty={qty}"
        )

    def _on_connect(self):
        self.client.cfg.update(
            {
                "client_role": self.cli_role_var.get(),
                "host": self.host_var.get().strip(),
                "port": int(self.port_var.get().strip()),
                "sender_comp_id": self.sender_var.get().strip(),
                "target_comp_id": self.target_var.get().strip(),
                "username": self.user_var.get().strip(),
                "password": self.pass_var.get().strip(),
                "heartbeat_interval": int(self.cli_hb_var.get().strip()),
                "client_reset_seq": self.cli_reset_seq_var.get(),
            }
        )
        self.connect_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.NORMAL)
        asyncio.run_coroutine_threadsafe(self._do_connect(), self.loop)

    async def _do_connect(self):
        ok = await self.client.connect()
        if not ok:
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)

    def _on_disconnect(self):
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)

    def _on_start_server(self):
        self.server.cfg.update(
            {
                "server_role": self.srv_role_var.get(),
                "server_host": self.srv_host_var.get().strip(),
                "server_port": int(self.srv_port_var.get().strip()),
                "server_sender_comp_id": self.srv_sender_var.get().strip(),
                "server_target_comp_id": self.srv_target_var.get().strip(),
                "server_target_host": self.srv_tgt_host_var.get().strip(),
                "server_target_port": int(self.srv_tgt_port_var.get().strip()),
                "heartbeat_interval": int(self.srv_hb_var.get().strip()),
                "server_reset_seq": self.srv_reset_seq_var.get(),
            }
        )
        self.start_srv_btn.config(state=tk.DISABLED)
        self.stop_srv_btn.config(state=tk.NORMAL)
        asyncio.run_coroutine_threadsafe(self._do_start_server(), self.loop)

    async def _do_start_server(self):
        await self.server.start()
        role = self.server.cfg.get("server_role", "ACCEPTOR")
        if role == "ACCEPTOR":
            self._log_server(
                f"Server (acceptor) listening on {self.server.cfg['server_host']}:"
                f"{self.server.cfg['server_port']}"
            )
        else:
            self._log_server(
                f"Server (initiator) connecting to "
                f"{self.server.cfg['server_target_host']}:"
                f"{self.server.cfg['server_target_port']}"
            )

    def _on_stop_server(self):
        self.start_srv_btn.config(state=tk.NORMAL)
        self.stop_srv_btn.config(state=tk.DISABLED)
        asyncio.run_coroutine_threadsafe(self.server.stop(), self.loop)
        self._log_server("Server stopped")

    def _on_close(self):
        asyncio.run_coroutine_threadsafe(self._do_close(), self.loop)
        self.root.destroy()

    async def _do_close(self):
        await self.server.stop()
        await self.client.disconnect()
