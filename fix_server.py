import asyncio
import logging
import random
import string
from datetime import datetime, timezone

import simplefix

logger = logging.getLogger(__name__)


def _ts():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]


def _gen_exec_id():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"EXEC{ts}{rand}"


def _gen_order_id():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    rand = "".join(random.choices(string.digits, k=6))
    return f"ORD{ts}{rand}"


def _parse_fix(data):
    parser = simplefix.FixParser()
    parser.append_buffer(data)
    return parser.get_message()


def _make_standard_header(msg, sender, target, seq, msg_type):
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, msg_type)
    msg.append_pair(49, sender)
    msg.append_pair(56, target)
    msg.append_pair(34, seq)
    msg.append_pair(52, _ts())


def _make_logon(sender, target, username, password, heartbeat=30, reset_seq=True):
    msg = simplefix.FixMessage()
    _make_standard_header(msg, sender, target, 1, "A")
    msg.append_pair(98, 0)
    msg.append_pair(108, heartbeat)
    msg.append_pair(553, username)
    msg.append_pair(554, password)
    if reset_seq:
        msg.append_pair(141, "Y")
    return msg


class FixServerSession:
    def __init__(self, reader, writer, server, on_order, is_initiator=False):
        self._reader = reader
        self._writer = writer
        self._server = server
        self._on_order = on_order
        self._send_lock = asyncio.Lock()
        self._seq_out = 1
        self._seq_in = 0
        self._logged_on = False
        self._hb_task = None
        self._reader_task = None
        self._sender_comp = None
        self._target_comp = None
        self._is_initiator = is_initiator

    @property
    def connected(self):
        return self._logged_on

    @property
    def sender_comp(self):
        return self._sender_comp

    @property
    def target_comp(self):
        return self._target_comp

    async def start(self):
        self._reader_task = asyncio.create_task(self._read_loop())

    async def stop(self):
        self._logged_on = False
        if self._hb_task:
            self._hb_task.cancel()
            self._hb_task = None
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass

    async def send_execution_report(
        self, clord_id, symbol, side, qty, ord_type, price,
        exec_type, ord_status, text="",
        last_qty=None, last_px=None, cum_qty=None, leaves_qty=None,
        order_id=None, exec_id=None, transact_time=None,
    ):
        if order_id is None:
            order_id = _gen_order_id()
        if exec_id is None:
            exec_id = _gen_exec_id()
        if transact_time is None:
            transact_time = _ts()
        msg = simplefix.FixMessage()
        _make_standard_header(msg, self._target_comp, self._sender_comp,
                              self._seq_out, "8")
        msg.append_pair(37, order_id)
        msg.append_pair(11, clord_id)
        msg.append_pair(17, exec_id)
        msg.append_pair(150, exec_type)
        msg.append_pair(39, ord_status)
        msg.append_pair(55, symbol)
        msg.append_pair(54, side)
        msg.append_pair(38, qty)
        msg.append_pair(40, ord_type)
        if price > 0:
            msg.append_pair(44, price)
        msg.append_pair(32, str(last_qty) if last_qty is not None else "0")
        msg.append_pair(31, str(last_px) if last_px is not None else "0")
        msg.append_pair(151, str(leaves_qty) if leaves_qty is not None else "0")
        msg.append_pair(14, str(cum_qty) if cum_qty is not None else "0")
        msg.append_pair(60, transact_time)
        if text:
            msg.append_pair(58, text)
        await self._send_raw(msg)
        self._seq_out += 1
        return {"order_id": order_id, "exec_id": exec_id, "transact_time": transact_time}

    async def _send_raw(self, msg):
        data = msg.encode()
        async with self._send_lock:
            if self._writer:
                self._writer.write(data)
                await self._writer.drain()

    async def _send(self, msg_type, body_fn):
        msg = simplefix.FixMessage()
        _make_standard_header(msg, self._target_comp, self._sender_comp,
                              self._seq_out, msg_type)
        body_fn(msg)
        await self._send_raw(msg)
        self._seq_out += 1

    async def _read_loop(self):
        buffer = b""
        while self._writer and not self._writer.is_closing():
            try:
                chunk = await self._reader.read(4096)
                if not chunk:
                    break
                buffer += chunk
                while True:
                    msg = _parse_fix(buffer)
                    if msg is None:
                        break
                    msg_bytes = msg.encode()
                    idx = buffer.find(msg_bytes)
                    if idx >= 0:
                        buffer = buffer[idx + len(msg_bytes) :]
                    await self._handle_message(msg)
            except (asyncio.CancelledError, ConnectionError):
                break
            except Exception as e:
                logger.error("Session read error: %s", e)
                break
        self._logged_on = False
        logger.info("Session %s disconnected", self._sender_comp)

    async def _handle_message(self, msg):
        msg_type = msg.get(35)
        if msg_type is None:
            return

        self._seq_in += 1

        v49 = msg.get(49)
        v56 = msg.get(56)
        sender = v49.decode() if v49 else ""
        target = v56.decode() if v56 else ""
        if not self._sender_comp:
            self._sender_comp = sender
            self._target_comp = target

        if msg_type == b"A":
            if self._logged_on:
                return
            self._logged_on = True
            logger.info("Logon from %s", sender)
            self._hb_task = asyncio.create_task(self._heartbeat_loop())

            if self._is_initiator:
                return

            rsp = simplefix.FixMessage()
            _make_standard_header(rsp, self._target_comp, self._sender_comp,
                                  self._seq_out, "A")
            rsp.append_pair(98, 0)
            rsp.append_pair(108, 30)
            if self._server.cfg.get("server_reset_seq", True):
                rsp.append_pair(141, "Y")
            await self._send_raw(rsp)
            self._seq_out += 1

        elif msg_type == b"0":
            pass

        elif msg_type == b"1":
            await self._send("0", lambda m: None)

        elif msg_type == b"5":
            await self._send("5", lambda m: None)
            self._logged_on = False

        elif msg_type == b"D":
            def _d(t): v = msg.get(t); return v.decode() if v else ""
            clord_id = _d(11)
            symbol = _d(55)
            side = _d(54)
            qty = _d(38)
            ord_type = _d(40)
            price_raw = _d(44)
            price = float(price_raw) if price_raw else 0.0
            handl_inst = _d(21)
            time_in_force = _d(59)
            sending_time = _d(52)

            order = {
                "clord_id": clord_id,
                "symbol": symbol,
                "side": side,
                "qty": float(qty),
                "ord_type": ord_type,
                "price": price,
                "handl_inst": handl_inst,
                "time_in_force": time_in_force,
                "status": "Pending",
                "session": self,
                "sending_time": sending_time,
            }
            self._server._orders[clord_id] = order
            logger.info("Received order ClOrdID=%s %s %s qty=%s",
                        clord_id, symbol, side, qty)
            if self._on_order:
                r = self._on_order(order)
                if r is not None:
                    await r

        elif msg_type == b"F":
            def _d(t): v = msg.get(t); return v.decode() if v else ""
            orig_clord = _d(41)
            symbol = _d(55)
            side = _d(54)
            qty = _d(38)
            clord_id = _d(11)

            order = self._server._orders.get(orig_clord)
            if order:
                order["_prev_status"] = order.get("status", "Pending")
                order["status"] = "CancelPending"
                order["_pending"] = {"action": "cancel"}
                logger.info("CancelRequest for ClOrdID=%s", orig_clord)
                if self._on_order:
                    r = self._on_order(order)
                    if r is not None:
                        await r
            else:
                logger.warning("CancelRequest for unknown order %s", orig_clord)

        elif msg_type == b"G":
            def _d(t): v = msg.get(t); return v.decode() if v else ""
            orig_clord = _d(41)
            new_clord = _d(11)
            symbol = _d(55)
            side = _d(54)
            qty = _d(38)
            ord_type = _d(40)
            price_raw = _d(44)
            price = float(price_raw) if price_raw else 0.0

            order = self._server._orders.get(orig_clord)
            if order:
                sym = symbol or order["symbol"]
                sd = side or order["side"]
                qt = float(qty) if qty else order["qty"]
                ot = ord_type or order["ord_type"]
                pr = price if price else order["price"]
                order["_prev_status"] = order.get("status", "Pending")
                order["status"] = "ModifyPending"
                order["_pending"] = {
                    "action": "modify",
                    "symbol": sym, "side": sd, "qty": qt,
                    "ord_type": ot, "price": pr,
                    "new_clord_id": new_clord,
                }
                logger.info("ModifyRequest for ClOrdID=%s", orig_clord)
                if self._on_order:
                    r = self._on_order(order)
                    if r is not None:
                        await r
            else:
                logger.warning("CancelReplaceRequest for unknown order %s", orig_clord)

    async def _heartbeat_loop(self):
        try:
            while self._logged_on:
                await asyncio.sleep(30)
                if self._logged_on:
                    await self._send("0", lambda m: None)
        except asyncio.CancelledError:
            pass


class FixServer:
    def __init__(self, config, on_order=None, on_status=None):
        self.cfg = config
        self._on_order = on_order
        self._on_status = on_status
        self._server = None
        self._sessions = []
        self._orders = {}
        self._running = False
        self._initiator_session = None

    @property
    def running(self):
        return self._running

    @property
    def orders(self):
        return list(self._orders.values())

    async def start(self):
        role = self.cfg.get("server_role", "ACCEPTOR")
        if role == "INITIATOR":
            return await self._start_as_initiator()
        return await self._start_as_acceptor()

    async def _start_as_acceptor(self):
        host = self.cfg.get("server_host", "127.0.0.1")
        port = int(self.cfg.get("server_port", 9823))
        self._server = await asyncio.start_server(
            self._on_connect, host=host, port=port,
        )
        self._running = True
        addr = self._server.sockets[0].getsockname()
        logger.info("FIX server (acceptor) listening on %s:%s", *addr)
        self._status(f"acceptor listening on {addr[0]}:{addr[1]}")
        return True

    async def _start_as_initiator(self):
        target_host = self.cfg.get("server_target_host", "127.0.0.1")
        target_port = int(self.cfg.get("server_target_port", 9824))
        try:
            reader, writer = await asyncio.open_connection(target_host, target_port)
            self._running = True
            logger.info("FIX server (initiator) connected to %s:%s",
                        target_host, target_port)

            sender = self.cfg.get("server_sender_comp_id", "SERVER")
            target = self.cfg.get("server_target_comp_id", "CLIENT")

            session = FixServerSession(reader, writer, self, self._on_order,
                                       is_initiator=True)
            session._sender_comp = sender
            session._target_comp = target
            self._initiator_session = session
            self._sessions.append(session)

            logon = _make_logon(
                sender, target,
                self.cfg.get("username", "user"),
                self.cfg.get("password", "password"),
                self.cfg.get("heartbeat_interval", 30),
                reset_seq=self.cfg.get("server_reset_seq", True),
            )
            await session._send_raw(logon)
            session._seq_out += 1
            logger.info("Initiator: logon sent")

            await session.start()
            self._status(f"initiator connected to {target_host}:{target_port}")
            return True
        except OSError as e:
            self._status(f"initiator connect failed: {e}")
            logger.error("Initiator connect failed: %s", e)
            return False

    async def stop(self):
        self._running = False
        for sess in self._sessions:
            await sess.stop()
        self._sessions.clear()
        self._initiator_session = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._status("server stopped")

    async def acknowledge_order(self, clord_id, text=""):
        order = self._orders.get(clord_id)
        if not order:
            return
        session = order["session"]
        order_id = _gen_order_id()
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "0", "0", text,
            order_id=order_id, exec_id=exec_id, transact_time=transact_time,
        )
        order["order_id"] = order_id
        order["exec_id"] = exec_id
        order["last_px"] = 0.0
        order["leaves_qty"] = float(order["qty"])
        order["transact_time"] = transact_time
        order["status"] = "Acknowledged"
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def reject_order(self, clord_id, text="Rejected"):
        order = self._orders.get(clord_id)
        if not order:
            return
        session = order["session"]
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "8", "8", text,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        order["exec_id"] = exec_id
        order["last_px"] = 0.0
        order["leaves_qty"] = float(order["qty"])
        order["transact_time"] = transact_time
        order["status"] = "Rejected"
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def execute_order(self, clord_id, executed_qty, executed_price, text="Executed"):
        order = self._orders.get(clord_id)
        if not order:
            return
        session = order["session"]
        total_qty = float(order["qty"])
        leaves = max(0.0, total_qty - float(executed_qty))
        if leaves == 0:
            exec_type = "2"
            ord_status = "2"
        else:
            exec_type = "1"
            ord_status = "1"
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            exec_type, ord_status, text,
            last_qty=executed_qty, last_px=executed_price,
            cum_qty=executed_qty, leaves_qty=leaves,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        order["exec_id"] = exec_id
        order["last_px"] = float(executed_price)
        order["leaves_qty"] = leaves
        order["transact_time"] = transact_time
        order["status"] = "Filled" if leaves == 0 else "PartiallyFilled"
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def approve_cancel(self, clord_id, text="Canceled"):
        order = self._orders.get(clord_id)
        if not order or order.get("status") != "CancelPending":
            return
        session = order["session"]
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "4", "4", text,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        order["exec_id"] = exec_id
        order["leaves_qty"] = 0.0
        order["transact_time"] = transact_time
        order["status"] = "Canceled"
        order.pop("_pending", None)
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def reject_cancel(self, clord_id, text="Cancel rejected"):
        order = self._orders.get(clord_id)
        if not order or order.get("status") != "CancelPending":
            return
        session = order["session"]
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "8", "0", text,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        order["exec_id"] = exec_id
        order["transact_time"] = transact_time
        order["status"] = order.get("_prev_status", "Pending")
        order.pop("_pending", None)
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def approve_modify(self, clord_id, text="Modified"):
        order = self._orders.get(clord_id)
        if not order or order.get("status") != "ModifyPending":
            return
        session = order["session"]
        pending = order.get("_pending", {})
        sym = pending.get("symbol", order["symbol"])
        sd = pending.get("side", order["side"])
        qt = pending.get("qty", order["qty"])
        ot = pending.get("ord_type", order["ord_type"])
        pr = pending.get("price", order["price"])
        order.update(symbol=sym, side=sd, qty=qt, ord_type=ot, price=pr)
        new_cid = pending.get("new_clord_id", order["clord_id"])
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "5", "5", text,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        if new_cid != order["clord_id"]:
            self._orders[new_cid] = order
            if clord_id != new_cid:
                self._orders.pop(clord_id, None)
            order["clord_id"] = new_cid
        order["exec_id"] = exec_id
        order["transact_time"] = transact_time
        order["status"] = "Modified"
        order.pop("_pending", None)
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def reject_modify(self, clord_id, text="Modify rejected"):
        order = self._orders.get(clord_id)
        if not order or order.get("status") != "ModifyPending":
            return
        session = order["session"]
        exec_id = _gen_exec_id()
        transact_time = _ts()
        await session.send_execution_report(
            order["clord_id"], order["symbol"], order["side"],
            order["qty"], order["ord_type"], order["price"],
            "8", "0", text,
            order_id=order.get("order_id"), exec_id=exec_id,
            transact_time=transact_time,
        )
        order["exec_id"] = exec_id
        order["transact_time"] = transact_time
        order["status"] = order.get("_prev_status", "Pending")
        order.pop("_pending", None)
        if self._on_order:
            r = self._on_order(order)
            if r is not None:
                await r

    async def _on_connect(self, reader, writer):
        session = FixServerSession(reader, writer, self, self._on_order,
                                   is_initiator=False)
        self._sessions.append(session)
        await session.start()

    def _status(self, s):
        if self._on_status:
            self._on_status(s)
