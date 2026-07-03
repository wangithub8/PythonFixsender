import asyncio
import logging
import random
import string
from datetime import datetime, timezone

import simplefix

logger = logging.getLogger(__name__)


def gen_clordid():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    rand = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD{ts}{rand}"


def fix_tag(tag, value):
    return f"{tag}={value}\x01"


def make_logon(sender, target, username, password, heartbeat=30, reset_seq=True):
    msg = simplefix.FixMessage()
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, "A")
    msg.append_pair(49, sender)
    msg.append_pair(56, target)
    msg.append_pair(34, 1)
    msg.append_pair(52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])
    msg.append_pair(98, 0)
    msg.append_pair(108, heartbeat)
    msg.append_pair(553, username)
    msg.append_pair(554, password)
    if reset_seq:
        msg.append_pair(141, "Y")
    return msg


def make_heartbeat(sender, target, seq):
    msg = simplefix.FixMessage()
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, "0")
    msg.append_pair(49, sender)
    msg.append_pair(56, target)
    msg.append_pair(34, seq)
    msg.append_pair(52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])
    return msg


def make_test_request(sender, target, seq, test_req_id):
    msg = simplefix.FixMessage()
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, "1")
    msg.append_pair(49, sender)
    msg.append_pair(56, target)
    msg.append_pair(34, seq)
    msg.append_pair(52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])
    msg.append_pair(112, test_req_id)
    return msg


def make_new_order_single(
    sender, target, seq, symbol, side, order_qty, ord_type, price, clord_id,
    account=None, handl_inst="1", time_in_force="0"
):
    msg = simplefix.FixMessage()
    msg.append_pair(8, "FIX.4.4")
    msg.append_pair(35, "D")
    msg.append_pair(49, sender)
    msg.append_pair(56, target)
    msg.append_pair(34, seq)
    msg.append_pair(52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])

    msg.append_pair(11, clord_id)
    msg.append_pair(21, handl_inst)
    msg.append_pair(55, symbol)
    msg.append_pair(54, side)
    msg.append_pair(38, order_qty)
    msg.append_pair(40, ord_type)
    msg.append_pair(59, time_in_force)
    msg.append_pair(60, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])

    if price > 0:
        msg.append_pair(44, price)

    if account:
        msg.append_pair(1, account)

    return msg


def parse_fix(data):
    parser = simplefix.FixParser()
    parser.append_buffer(data)
    return parser.get_message()


class FixClient:
    def __init__(self, config, on_message=None, on_status=None, on_order_update=None):
        self.cfg = config
        self._on_message = on_message
        self._on_status = on_status
        self._on_order_update = on_order_update
        self._reader = None
        self._writer = None
        self._seq_out = 1
        self._seq_in = 1
        self._connected = False
        self._logged_on = False
        self._hb_task = None
        self._reader_task = None
        self._send_lock = asyncio.Lock()
        self._clordid_counter = 0
        self._sent_orders = {}

    async def connect(self):
        role = self.cfg.get("client_role", "INITIATOR")
        if role == "ACCEPTOR":
            return await self._connect_as_acceptor()
        return await self._connect_as_initiator()

    async def _connect_as_initiator(self):
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.cfg["host"], self.cfg["port"]
            )
            self._connected = True
            self._seq_out = 1
            self._seq_in = 1
            self._status("connected")
            logger.info("TCP connected to %s:%s", self.cfg["host"], self.cfg["port"])

            await self._send_raw(
                make_logon(
                    self.cfg["sender_comp_id"],
                    self.cfg["target_comp_id"],
                    self.cfg["username"],
                    self.cfg["password"],
                    self.cfg.get("heartbeat_interval", 30),
                    reset_seq=self.cfg.get("client_reset_seq", True),
                )
            )
            self._seq_out += 1
            logger.info("Logon sent, awaiting response...")

            self._reader_task = asyncio.create_task(self._read_loop())
            return True

        except OSError as e:
            self._status(f"connection failed: {e}")
            logger.error("Connection failed: %s", e)
            return False

    async def _connect_as_acceptor(self):
        try:
            srv = await asyncio.start_server(
                self._on_acceptor_connect,
                self.cfg["host"], int(self.cfg["port"]),
            )
            self._acceptor_server = srv
            self._status("listening")
            logger.info("Client acceptor listening on %s:%s",
                        self.cfg["host"], self.cfg["port"])
            return True
        except OSError as e:
            self._status(f"listen failed: {e}")
            logger.error("Acceptor listen failed: %s", e)
            return False

    async def _on_acceptor_connect(self, reader, writer):
        self._reader = reader
        self._writer = writer
        self._connected = True
        self._seq_out = 1
        self._seq_in = 1
        self._status("incoming connection")
        logger.info("Acceptor got incoming connection")
        self._reader_task = asyncio.create_task(self._read_loop())

    async def disconnect(self):
        self._logged_on = False
        if hasattr(self, "_acceptor_server") and self._acceptor_server:
            self._acceptor_server.close()
            await self._acceptor_server.wait_closed()
            self._acceptor_server = None
        if self._hb_task:
            self._hb_task.cancel()
            self._hb_task = None
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._connected = False
        self._status("disconnected")

    async def _send_raw(self, msg):
        data = msg.encode()
        async with self._send_lock:
            if self._writer:
                self._writer.write(data)
                await self._writer.drain()

    async def _send(self, msg_type, body_fn):
        msg = simplefix.FixMessage()
        msg.append_pair(8, "FIX.4.4")
        msg.append_pair(35, msg_type)
        msg.append_pair(49, self.cfg["sender_comp_id"])
        msg.append_pair(56, self.cfg["target_comp_id"])
        msg.append_pair(34, self._seq_out)
        msg.append_pair(
            52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]
        )
        body_fn(msg)
        await self._send_raw(msg)
        self._seq_out += 1

    async def send_order(self, symbol, side, qty, ord_type, price=0.0, account=None,
                        handl_inst="1", time_in_force="0"):
        clord_id = gen_clordid()
        sending_time = datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]
        await self._send("D", lambda m: (
            m.append_pair(11, clord_id),
            m.append_pair(21, handl_inst),
            m.append_pair(55, symbol),
            m.append_pair(54, side),
            m.append_pair(38, qty),
            m.append_pair(40, ord_type),
            m.append_pair(59, time_in_force),
            m.append_pair(60, sending_time),
            m.append_pair(44, price) if price > 0 else None,
            m.append_pair(1, account) if account else None,
        ))
        self._sent_orders[clord_id] = {
            "symbol": symbol, "side": side, "qty": qty,
            "type": ord_type, "price": price, "status": "Sent",
            "sending_time": sending_time,
            "handl_inst": handl_inst, "time_in_force": time_in_force,
        }
        self._notify_order_update(clord_id)
        return clord_id

    async def cancel_order(self, clord_id):
        order = self._sent_orders.get(clord_id)
        if not order:
            return
        cancel_id = gen_clordid()
        await self._send("F", lambda m: (
            m.append_pair(11, cancel_id),
            m.append_pair(41, clord_id),
            m.append_pair(55, order["symbol"]),
            m.append_pair(54, order["side"]),
            m.append_pair(38, order["qty"]),
            m.append_pair(60, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]),
        ))
        order["status"] = "CancelPending"
        self._notify_order_update(clord_id)

    async def modify_order(self, clord_id, symbol, side, qty, ord_type, price=0.0):
        order = self._sent_orders.get(clord_id)
        if not order:
            return
        new_clord_id = gen_clordid()
        await self._send("G", lambda m: (
            m.append_pair(11, new_clord_id),
            m.append_pair(41, clord_id),
            m.append_pair(55, symbol),
            m.append_pair(54, side),
            m.append_pair(38, qty),
            m.append_pair(40, ord_type),
            m.append_pair(60, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21]),
            m.append_pair(44, price) if price > 0 else None,
        ))
        order["status"] = "ModifyPending"
        self._notify_order_update(clord_id)

    def _notify_order_update(self, clord_id):
        if self._on_order_update:
            order = self._sent_orders.get(clord_id)
            if order:
                self._on_order_update(clord_id, dict(order))

    async def _read_loop(self):
        buffer = b""
        while self._connected and self._reader:
            try:
                chunk = await self._reader.read(4096)
                if not chunk:
                    logger.info("Connection closed by peer")
                    break
                buffer += chunk
                while True:
                    msg = parse_fix(buffer)
                    if msg is None:
                        break
                    consumed = buffer.find(b"\x018=FIX")
                    if consumed > 0:
                        buffer = buffer[consumed:]
                    msg_bytes = msg.encode()
                    idx = buffer.find(msg_bytes)
                    if idx >= 0:
                        buffer = buffer[idx + len(msg_bytes) :]
                    await self._handle_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Read error: %s", e)
                break
        self._status("disconnected")
        self._logged_on = False

    async def _handle_message(self, msg):
        msg_type = msg.get(35)
        if msg_type is None:
            return

        self._seq_in += 1
        logger.info("RX: %s", msg_type)

        if msg_type == b"A":
            role = self.cfg.get("client_role", "INITIATOR")
            if role == "ACCEPTOR":
                rsp = simplefix.FixMessage()
                rsp.append_pair(8, "FIX.4.4")
                rsp.append_pair(35, "A")
                rsp.append_pair(49, self.cfg["sender_comp_id"])
                rsp.append_pair(56, self.cfg["target_comp_id"])
                rsp.append_pair(34, self._seq_out)
                rsp.append_pair(52, datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:21])
                rsp.append_pair(98, 0)
                rsp.append_pair(108, self.cfg.get("heartbeat_interval", 30))
                if self.cfg.get("client_reset_seq", True):
                    rsp.append_pair(141, "Y")
                await self._send_raw(rsp)
                self._seq_out += 1
                logger.info("Acceptor: logon response sent")
            self._logged_on = True
            self._status("logged on")
            logger.info("Logon confirmed")
            self._hb_task = asyncio.create_task(self._heartbeat_loop())

        elif msg_type == b"0":
            pass

        elif msg_type == b"1":
            v = msg.get(112)
            test_id = v.decode() if v else ""
            async with self._send_lock:
                hb = make_heartbeat(
                    self.cfg["sender_comp_id"],
                    self.cfg["target_comp_id"],
                    self._seq_out,
                )
                await self._send_raw(hb)
                self._seq_out += 1

        elif msg_type == b"3":
            logger.warning("Logout received")

        elif msg_type == b"5":
            await self._send("5", lambda m: None)
            self._seq_out += 1

        elif msg_type == b"8":
            clord_id = msg.get(11)
            if clord_id:
                cid = clord_id.decode()
                if cid in self._sent_orders:
                    def _d(t): v = msg.get(t); return v.decode() if v else ""
                    order_id = _d(37)
                    exec_id = _d(17)
                    last_px = _d(31)
                    leaves_qty = _d(151)
                    transact_time = _d(60)
                    if order_id:
                        self._sent_orders[cid]["order_id"] = order_id
                    if exec_id:
                        self._sent_orders[cid]["exec_id"] = exec_id
                    if last_px:
                        self._sent_orders[cid]["last_px"] = float(last_px)
                    if leaves_qty:
                        self._sent_orders[cid]["leaves_qty"] = float(leaves_qty)
                    if transact_time:
                        self._sent_orders[cid]["transact_time"] = transact_time
                    ord_status = msg.get(39)
                    if ord_status:
                        st = ord_status.decode()
                        status_map = {
                            "0": "New", "1": "PartiallyFilled", "2": "Filled",
                            "4": "Canceled", "5": "Replaced", "6": "PendingCancel",
                            "8": "Rejected", "A": "PendingNew",
                        }
                        self._sent_orders[cid]["status"] = status_map.get(st, st)
                    self._notify_order_update(cid)

        if self._on_message:
            r = self._on_message(msg)
            if r is not None:
                await r

    async def _heartbeat_loop(self):
        interval = self.cfg.get("heartbeat_interval", 30)
        try:
            while self._logged_on:
                await asyncio.sleep(interval)
                if self._logged_on:
                    hb = make_heartbeat(
                        self.cfg["sender_comp_id"],
                        self.cfg["target_comp_id"],
                        self._seq_out,
                    )
                    await self._send_raw(hb)
                    self._seq_out += 1
        except asyncio.CancelledError:
            pass

    def _status(self, s):
        if self._on_status:
            self._on_status(s)
