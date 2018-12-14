import curses
import os
import time
import json

from redis import StrictRedis

redis_client = StrictRedis()
redis_pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
statuses = {}
FLOOD_MODE = "FLOOD" in os.environ

class TerminalColor:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def on_warrior_message(message):
    data = json.loads(message["data"])
    status_key = "%s:%s" % (data["host"], data["port"])

    # Split the message
    output_split = data["data"].split(" ")

    # Bad code to priortize uploads on the display.
    if "%" not in data["data"] or "B/s" not in data["data"]:
        if status_key in statuses and ("%" in statuses[status_key][0] and "B/s" in statuses[status_key][0]):
            if "100%" not in statuses[status_key][0]:
                return

    # Change the color depending on status.
    # XXX FUCKING NASTY
    if "=404" in output_split[0]:
        status_color = TerminalColor.FAIL
    elif "=301" in output_split[0]:
        status_color = TerminalColor.WARNING
    elif "%" in data["data"] and "B/s" in data["data"]:
        status_color = TerminalColor.OKBLUE
    else:
        status_color = ""

    output = "{status_color}{host}:{port}{extra}\t {data}{endc}".format(
        host=data["host"],
        port=data["port"],
        data=data["data"].strip(),
        status_color=status_color,
        endc=TerminalColor.ENDC if FLOOD_MODE else "",
        extra="\t" + data["item_id"] if FLOOD_MODE else ""
    )

    if FLOOD_MODE:
        print(output)
    else:
        statuses[status_key] = (output, data["item_id"])

def draw_statuses(console):
    console.clear()
    console.refresh()
    height, width = console.getmaxyx()
    max_values = int(width // 1.75)

    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    while True:
        i = 1
        console.addstr(0, 0, "Host\t\t\t URL")
        console.addstr(0, max_values, "\tItem")

        for host in sorted(statuses):
            values, item_id = statuses[host]
            color_pair = curses.color_pair(1)

            if values.startswith(TerminalColor.OKBLUE):
                values = values.lstrip(TerminalColor.OKBLUE)
                color_pair = curses.color_pair(2)
            elif values.startswith(TerminalColor.FAIL):
                values = values.lstrip(TerminalColor.FAIL)
                color_pair = curses.color_pair(3)
            elif values.startswith(TerminalColor.WARNING):
                values = values.lstrip(TerminalColor.WARNING)
                color_pair = curses.color_pair(4)

            # Truncate if the string is longer than 75%
            if len(values) >= max_values:
                values = values[:max_values - 12].strip() + "..."

            # Print out host and values
            console.addstr(i, 0, values, color_pair)
            console.clrtoeol()

            # Print posts remaining
            console.addstr(i, max_values, "\t" + item_id)

            i += 1
        console.refresh()
        time.sleep(0.1)

redis_pubsub.subscribe(**{"tumblr:warrior": on_warrior_message})
pubsub_thread = redis_pubsub.run_in_thread(sleep_time=0.001)

try:
    if "FLOOD" in os.environ:
        pubsub_thread.join()
    else:
        curses.wrapper(draw_statuses)
except KeyboardInterrupt:
    pubsub_thread.stop()
