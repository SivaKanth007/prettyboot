"""Synthesize an asciinema v2 cast of a prettyboot CLI session
(real captured outputs, simulated typing)."""
import json
import random

random.seed(7)

PROMPT = "[1;32m$[0m "
t = 0.6
events = []


def out(data, dt=0.0):
    global t
    t += dt
    events.append([round(t, 3), "o", data])


def type_cmd(cmd):
    global t
    out(PROMPT)
    for ch in cmd:
        out(ch, dt=random.uniform(0.035, 0.09))
    t += 0.35
    out("\r\n")


def output_lines(lines, hold=1.3):
    global t
    t += 0.12
    for ln in lines:
        out(ln + "\r\n")
    t += hold


type_cmd("sudo prettyboot list")
output_lines(["* ✓ mac-dark", "  ✓ mac-light"])

type_cmd("sudo prettyboot use mac-light")
output_lines(["Active theme: mac-light"])

type_cmd("sudo prettyboot next")
output_lines(["Active theme: mac-dark"])

type_cmd("sudo prettyboot timeout 10")
output_lines(["Timeout: 10"], hold=0.4)

out(PROMPT, dt=0.2)
t += 2.6
out("", dt=0.0)

header = {"version": 2, "width": 56, "height": 14,
          "title": "prettyboot CLI demo"}
with open("cli-demo.cast", "w") as fh:
    fh.write(json.dumps(header) + "\n")
    for ev in events:
        fh.write(json.dumps(ev) + "\n")
print("cast written, duration", round(t, 2), "s")
