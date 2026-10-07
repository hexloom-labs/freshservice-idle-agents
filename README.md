# Find inactive agents in Freshservice

A single Python file that lists the full-time Freshservice agents with no activity or login for 30 days (or the number you choose) and adds up what those seats cost. It reads your agent list and changes nothing.

Needs Python 3.8 or newer, no packages, and an admin API key. Not yet run against a live Freshservice account (see "How it was tested").

## Sample output

Five full-time sample agents, plus one occasional and one deactivated agent, with the clock set to 15 October 2026 and a price of 49 per agent per month:

```
3 of 5 full-time agents have shown no activity for 30 days or more.
  Nora Never                   nora@acme.test                     never seen
  Lena Long                    lena@acme.test                     2026-05-01 (167 days ago)
  Theo Thirty                  theo@acme.test                     2026-09-15 (30 days ago)
At 49.00 per agent per month these seats cost 147.00 a month (1764.00 a year).
Not counted: 1 occasional, 1 deactivated.
```

## Run it

```
python3 freshservice_idle_agents.py acme.freshservice.com --days 30 --price 49 --csv idle.csv
```

On Windows use `python` instead of `python3`, and run it from cmd or PowerShell, not Git Bash, so the key prompt stays hidden. When it asks for the API key (Profile settings, "Your API Key", signed in as an admin), paste it and press Enter.

Options: `--days` (1 to 365, default 30), `--price` (what you pay per full-time agent per month, any currency, optional), `--csv FILE` (optional; an existing file is overwritten).

## How it decides who is idle

- For each agent it takes the later of `last_active_at` and `last_login_at` from the Freshservice Agents API. Either can be empty.
- If that moment is at least N days ago, the agent is listed.
- An agent with neither date is listed as "never seen" once the agent's own account is at least N days old. If there is no creation date either, the agent cannot be judged and the script says how many were left out.
- Occasional and deactivated agents are not counted, because they are not full-time seats.
- Days are whole days counted back from the moment you run it. Dates are shown in UTC.

A late timestamp is not proof that a seat is in use, and an old one is not proof that it is idle for good. Treat the list as a place to start checking.

## What it does with your key

- It asks for the key at a hidden prompt, so the key is not on the command line and is not saved in your shell history. If you set `FRESHSERVICE_API_KEY` yourself instead, your shell may keep that line in its history.
- It sends the key only to the address you typed, and only if that address ends in `.freshservice.com`. It never follows a redirect to another host.
- It makes read-only requests for the agent list, 100 agents at a time, and stops after 5,000 agents. It does not deactivate, edit or delete anyone.
- If Freshservice rate limits the account, it stops and says so.

## How it was tested

Against sample agents only: paging, refusing addresses that are not Freshservice, never following a redirect, agent names in other alphabets, and a CSV file that shows names starting with `=`, `+`, `-` or `@` as text. It has not been run against a live Freshservice account. If it fails on yours, open an issue with what it printed (never your key).

## More

Guide with the same steps and a form for a Freshservice app that does this check inside Freshservice: https://hexloomlabs.com/seat-sweep/find-inactive-freshservice-agents/?ref=github

Written by Hexloom Labs with AI assistance (drafted by an AI agent, checked with tests and a written review). Freshservice is a trademark of Freshworks Inc.; this is an independent script and is not affiliated with or endorsed by Freshworks. MIT licence.
