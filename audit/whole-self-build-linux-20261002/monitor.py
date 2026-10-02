import datetime, hashlib, json, pathlib, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parent
RUN = 36961998100
HEAD = "5d14ae46f327a7f0ee1f9812b4ba62b73cf035bc"

def command(label, argv):
    out, err = ROOT / (label + ".json"), ROOT / (label + ".stderr")
    with out.open("xb") as stdout, err.open("xb") as stderr:
        result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=90)
    if result.returncode:
        raise RuntimeError(label + " failed; raw stderr retained")
    return json.loads(out.read_text())

previous = None
started = time.monotonic()
while time.monotonic() - started < 22500:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    value = command(stamp + "-monitor-run", ["gh", "api", f"repos/cyberia-to/trisha/actions/runs/{RUN}"])
    if value["head_sha"] != HEAD or value["run_attempt"] != 1 or value["event"] != "push":
        raise RuntimeError("Run identity changed")
    jobs = command(stamp + "-monitor-jobs", ["gh", "api", f"repos/cyberia-to/trisha/actions/runs/{RUN}/jobs?per_page=100"])
    summary = dict(run=RUN, status=value["status"], conclusion=value["conclusion"], jobs=[dict(id=j["id"], name=j["name"], status=j["status"], conclusion=j["conclusion"], active=[s["name"] for s in j["steps"] if s["status"] == "in_progress"]) for j in jobs["jobs"]])
    if summary != previous:
        print(json.dumps(dict(observed_at=stamp, **summary)), flush=True)
        previous = summary
    if value["status"] == "completed":
        (ROOT / "monitor-completed.json").write_text(json.dumps(dict(observed_at=stamp, **summary), indent=2) + "\n")
        break
    time.sleep(60)
else:
    raise RuntimeError("Local monitor deadline; remote jobs untouched")
