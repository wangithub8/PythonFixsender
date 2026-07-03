"""asyncIO FIX order entry client with tkinter GUI and integrated FIX server.

Runs asyncio event loop in the main thread and drives tkinter via root.after().
"""

import asyncio
import logging
import tkinter as tk

from config import load_config, save_config
from fix_client import FixClient
from fix_server import FixServer
from gui import FixOrderGui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class AsyncTkApp:
    def __init__(self):
        self.root = tk.Tk()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        config = load_config()

        self.server = FixServer(
            config,
            on_order=self._on_server_order,
            on_status=self._on_server_status,
        )

        self.client = FixClient(
            config,
            on_message=self._on_fix_message,
            on_status=self._on_client_status,
            on_order_update=self._on_client_order_update,
        )

        self.gui = FixOrderGui(self.root, self.client, self.server, self.loop)

    def _on_fix_message(self, msg):
        v = msg.get(35)
        msg_type = v.decode() if v else "?"
        self.root.after(0, self.gui._log_client, f"RX MsgType={msg_type}")
        return None

    def _on_client_status(self, status):
        self.root.after(0, self.gui.set_client_status, status)
        return None

    def _on_client_order_update(self, clord_id, order):
        self.root.after(0, self.gui.add_client_order, clord_id, order)
        return None

    def _on_server_order(self, order):
        self.root.after(0, self._update_order_gui, order)
        return None

    def _update_order_gui(self, order):
        iid = order["clord_id"]
        if self.gui.order_tree.exists(iid):
            self.gui.update_order(order)
        else:
            self.gui.add_order(order)

    def _on_server_status(self, status):
        self.root.after(0, self.gui.set_server_status, status)
        return None

    async def _tick(self):
        while True:
            self.root.update_idletasks()
            self.root.update()
            await asyncio.sleep(0.02)

    def run(self):
        try:
            self.loop.run_until_complete(self._tick())
        except (tk.TclError, KeyboardInterrupt):
            pass
        finally:
            self.loop.run_until_complete(self.server.stop())
            self.loop.run_until_complete(self.client.disconnect())
            self.loop.close()
            try:
                save_config(self.client.cfg)
            except Exception:
                pass


def main():
    app = AsyncTkApp()
    app.run()


if __name__ == "__main__":
    main()
